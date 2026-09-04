#!/usr/bin/env python3
"""Servidor MCP do vault Obsidian: a LLM le e grava a documentacao por aqui.

Zero dependencias: o protocolo MCP (JSON-RPC 2.0 sobre stdio, uma mensagem
por linha) e implementado so com a biblioteca padrao (Python 3.9+). Tudo e
filesystem — o Obsidian nao precisa estar aberto. As convencoes do vault
(pasta por tipo, nome com data, frontmatter, link e entrada no hub, Home,
commit -> pull --rebase -> push) vivem aqui, em codigo, nao na memoria do
modelo.

Registro no Claude Code (uma vez, escopo de usuario — vale em todo projeto):

  python mcp/servidor_vault.py --instalar
  python mcp/servidor_vault.py --instalar --vault <pasta de projetos do vault>

`--instalar` roda o `claude mcp add` com o python e o caminho absoluto certos.
O caminho do vault vem de `OBSIDIAN_VAULT` (a pasta de projetos, a mesma das
skills) ou de `--vault`. Caminho nunca e inventado.

Ferramentas:
  visao_geral     panorama: projetos, contagem por tipo, notas recentes
  buscar          full-text sem acento/caixa, filtros projeto/tipo/status
  listar_notas    metadados das notas, mais recentes primeiro
  ler_nota        conteudo integral (caminho relativo ou nome de wikilink)
  conexoes        wikilinks de saida e backlinks (navegacao no grafo)
  salvar_nota     cria a nota com tudo que a convencao exige (e hub/Home novos)
  atualizar_nota  corpo, status, tags, sucessora (obsoleta) ou resumo no hub
  mapa_codigo     mapa do codigo (graphify-out do repo, ponteiro Repo: do hub)
  consultar_codigo pergunta ao grafo via CLI graphify (query/explain/path)
  gerar_mapa      regrava a nota Mapa do Codigo preservando a Leitura curada

Vault que e repositorio git: cada gravacao faz commit -> pull --rebase -> push
(desligue com `--sem-git` no registro). Autoteste: mcp/teste_servidor_vault.py
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict

PROTOCOLOS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
PROTOCOLO_PADRAO = "2025-06-18"
IGNORAR = {".obsidian", ".scripts", ".git"}
# [[alvo]] e [[alvo|texto]]; blocos e trechos de codigo nao contam como link
WIKILINK_RE = re.compile(r"\[\[([^\]\[|#]+)")
CODEBLOCK_RE = re.compile(r"```.*?```", re.S)
INLINECODE_RE = re.compile(r"`[^`\n]+`")
DATA_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

VAULT = None  # resolvido em main()
SEM_GIT = False  # --sem-git: nunca commita nem empurra o vault


class ErroUso(Exception):
    """Chamada invalida: vira texto de erro para o modelo, nunca derruba o servidor."""

INSTRUCOES = (
    "Vault Obsidian com a documentacao dos projetos (specs, planos, ADRs, bugs, "
    "evolucoes, analises). Estrutura: Home.md -> <projeto>/<projeto>.md (hub) -> "
    "Specs/, Arquitetura/, Bugs/, Evolucoes/, Analises/. Ler: visao_geral, buscar, "
    "listar_notas, ler_nota, conexoes. Gravar: salvar_nota (nota nova; faz pasta, "
    "nome, frontmatter, hub, Home e git) e atualizar_nota (nota existente). "
    "Codigo: mapa_codigo (antes de mexer no projeto), consultar_codigo (arquitetura), "
    "gerar_mapa (apos o graphify); salvar_nota aceita arquivos= para citar componentes. "
    "Nunca escreva ou leia os arquivos do vault por fora destas ferramentas."
)

ERRO_VAULT = (
    "Vault nao configurado. Defina OBSIDIAN_VAULT apontando para a pasta de "
    'projetos do vault (ex.: export OBSIDIAN_VAULT="$HOME/obsidian/projetos") e '
    "reinicie o servidor MCP, ou registre-o com `--vault <caminho>` no fim do "
    "comando. O caminho nunca e inventado: pergunte ao usuario onde fica."
)


# ---------- leitura do vault ----------

def notas():
    """Todas as notas .md do vault, com frontmatter ja separado."""
    lista = []
    for raiz, dirs, arqs in os.walk(VAULT):
        dirs[:] = sorted(d for d in dirs if d not in IGNORAR)
        for a in sorted(arqs):
            if not a.lower().endswith(".md"):
                continue
            caminho = os.path.join(raiz, a)
            try:
                with open(caminho, encoding="utf-8") as f:
                    texto = f.read()
                mtime = os.path.getmtime(caminho)
            except (OSError, UnicodeDecodeError):
                continue
            rel = os.path.relpath(caminho, VAULT).replace(os.sep, "/")
            partes = rel.split("/")
            lista.append({
                "rel": rel,
                "nome": os.path.splitext(a)[0],
                "projeto": partes[0] if len(partes) > 1 else None,
                "fm": frontmatter(texto) or {},
                "texto": texto,
                "mtime": mtime,
            })
    return lista


def frontmatter(texto):
    if not texto.startswith("---"):
        return None
    fim = texto.find("\n---", 3)
    if fim == -1:
        return None
    campos = {}
    for linha in texto[3:fim].splitlines():
        if ":" in linha and not linha.startswith((" ", "-", "\t")):
            k, _, v = linha.partition(":")
            campos[k.strip()] = v.strip()
    return campos


def corpo_de(nota):
    """Texto da nota sem o frontmatter (para trechos legiveis)."""
    texto = nota["texto"]
    if texto.startswith("---"):
        fim = texto.find("\n---", 3)
        if fim != -1:
            return texto[fim + 4:].lstrip("\n")
    return texto


def data_de(nota):
    d = str(nota["fm"].get("data", ""))
    m = DATA_RE.search(d)
    if m:
        return m.group(0)
    return time.strftime("%Y-%m-%d", time.localtime(nota["mtime"]))


def sem_codigo(texto):
    return INLINECODE_RE.sub("", CODEBLOCK_RE.sub("", texto))


def links_de(texto):
    return {a.strip() for a in WIKILINK_RE.findall(sem_codigo(texto)) if a.strip()}


# ---------- busca ----------

def normalizar(s):
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").casefold()


def norm_com_mapa(s):
    """Versao normalizada + mapa de indice normalizado -> indice original."""
    saida, mapa = [], []
    for i, c in enumerate(s):
        for d in unicodedata.normalize("NFD", c):
            if unicodedata.category(d) == "Mn":
                continue
            for e in d.casefold():
                saida.append(e)
                mapa.append(i)
    return "".join(saida), mapa


def trecho(texto, termos):
    """Contexto ao redor da primeira ocorrencia de um dos termos."""
    norm, mapa = norm_com_mapa(texto)
    for termo in termos:
        pos = norm.find(termo)
        if pos < 0 or not mapa:
            continue
        ini = mapa[pos]
        fim = mapa[min(pos + len(termo), len(mapa)) - 1] + 1
        a, b = max(0, ini - 90), min(len(texto), fim + 90)
        t = " ".join(texto[a:b].split())
        return ("…" if a > 0 else "") + t + ("…" if b < len(texto) else "")
    return ""


def valores(v):
    return [normalizar(x.strip()) for x in str(v or "").split("|")]


def filtrar(todas, projeto=None, tipo=None, status=None):
    sel = todas
    if projeto:
        p = normalizar(projeto)
        sel = [n for n in sel if n["projeto"] and normalizar(n["projeto"]) == p]
    if tipo:
        t = normalizar(tipo)
        sel = [n for n in sel if t in valores(n["fm"].get("tipo"))]
    if status:
        s = normalizar(status)
        sel = [n for n in sel if s in valores(n["fm"].get("status"))]
    return sel


def rotulo_filtros(projeto, tipo, status):
    partes = [f"{k}={v}" for k, v in
              (("projeto", projeto), ("tipo", tipo), ("status", status)) if v]
    return " [" + ", ".join(partes) + "]" if partes else ""


def inteiro(v, padrao, teto):
    try:
        return max(1, min(int(v), teto))
    except (TypeError, ValueError):
        return padrao


def linha_meta(n):
    fm = n["fm"]
    proj = fm.get("projeto", n["projeto"] or "-")
    return (f"projeto: {proj} | tipo: {fm.get('tipo', '-')} | "
            f"status: {fm.get('status', '-')} | data: {data_de(n)}")


def achar(ref, todas):
    """Resolve caminho relativo ou nome de nota -> (nota, candidatos)."""
    ref = str(ref).strip().strip("/").replace("\\", "/")
    base = ref[:-3] if ref.lower().endswith(".md") else ref
    nr = normalizar(base)
    if not nr:
        return None, None
    for grupo in (
        [n for n in todas if n["rel"] == ref or n["rel"] == base + ".md"
         or n["nome"] == base],
        [n for n in todas if normalizar(n["nome"]) == nr
         or normalizar(n["rel"][:-3]) == nr],
        [n for n in todas if nr in normalizar(n["nome"])],
    ):
        if len(grupo) == 1:
            return grupo[0], None
        if grupo:
            return None, grupo
    return None, None


# ---------- ferramentas ----------

def visao_geral():
    todas = notas()
    if not todas:
        return f"Vault vazio (nenhuma nota .md em {VAULT})."
    projetos = defaultdict(list)
    for n in todas:
        if n["projeto"]:
            projetos[n["projeto"]].append(n)
    linhas = [f"Vault: {VAULT}",
              f"{len(projetos)} projeto(s), {len(todas)} nota(s)", ""]
    for proj in sorted(projetos):
        ns = projetos[proj]
        tipos = defaultdict(int)
        for n in ns:
            tipos[n["fm"].get("tipo") or "?"] += 1
        det = ", ".join(f"{t}: {c}" for t, c in sorted(tipos.items()))
        hub = "" if any(n["nome"] == proj for n in ns) else " | SEM HUB"
        linhas.append(f"- {proj} — {len(ns)} nota(s) ({det}){hub}")
    recentes = sorted(todas, key=data_de, reverse=True)[:6]
    linhas += ["", "Recentes:"]
    linhas += [f"- {data_de(n)}  {n['rel']}" for n in recentes]
    return "\n".join(linhas)


def buscar(consulta="", projeto=None, tipo=None, status=None, limite=None):
    termos = [normalizar(t) for t in str(consulta).split() if t]
    if not termos:
        return "Informe a consulta (um ou mais termos; todos precisam aparecer)."
    limite = inteiro(limite, 10, 30)
    achadas = []
    for n in filtrar(notas(), projeto, tipo, status):
        titulo, corpo = normalizar(n["nome"]), normalizar(n["texto"])
        if not all(t in titulo or t in corpo for t in termos):
            continue
        pontos = sum(5 for t in termos if t in titulo)
        pontos += sum(corpo.count(t) for t in termos)
        achadas.append((pontos, n))
    filtros = rotulo_filtros(projeto, tipo, status)
    if not achadas:
        return (f'Nenhuma nota para "{consulta}"{filtros}. Tente menos termos, '
                "sem filtros, ou visao_geral para ver o que existe.")
    achadas.sort(key=lambda par: (-par[0], par[1]["rel"]))
    linhas = [f'{len(achadas)} nota(s) para "{consulta}"{filtros}'
              + (f", mostrando {limite}:" if len(achadas) > limite else ":")]
    for _, n in achadas[:limite]:
        linhas.append(f"\n- {n['rel']}\n  {linha_meta(n)}")
        t = trecho(corpo_de(n), termos)
        if t:
            linhas.append(f'  "{t}"')
    return "\n".join(linhas)


def listar_notas(projeto=None, tipo=None, status=None, limite=None):
    limite = inteiro(limite, 20, 100)
    sel = filtrar(notas(), projeto, tipo, status)
    filtros = rotulo_filtros(projeto, tipo, status)
    if not sel:
        return (f"Nenhuma nota{filtros}. Confira os nomes com visao_geral "
                "(projeto = nome da pasta; tipo/status como no frontmatter).")
    sel.sort(key=data_de, reverse=True)
    linhas = [f"{min(limite, len(sel))} de {len(sel)} nota(s){filtros}, "
              "mais recentes primeiro:"]
    linhas += [f"- {n['rel']}\n  {linha_meta(n)}" for n in sel[:limite]]
    return "\n".join(linhas)


def ler_nota(nota=""):
    todas = notas()
    alvo, candidatos = achar(nota, todas)
    if alvo:
        return f"Caminho: {alvo['rel']}\n\n{alvo['texto']}"
    if candidatos:
        linhas = [f'Mais de uma nota bate com "{nota}" — repita com o caminho:']
        linhas += [f"- {n['rel']}" for n in candidatos[:10]]
        if len(candidatos) > 10:
            linhas.append(f"… e mais {len(candidatos) - 10}")
        return "\n".join(linhas)
    return (f'Nota nao encontrada: "{nota}". Aceito caminho relativo ao vault '
            "ou o nome como em wikilink; use buscar ou listar_notas para achar.")


def conexoes(nota=""):
    todas = notas()
    alvo, candidatos = achar(nota, todas)
    if not alvo:
        if candidatos:
            linhas = [f'Mais de uma nota bate com "{nota}" — repita com o caminho:']
            linhas += [f"- {n['rel']}" for n in candidatos[:10]]
            return "\n".join(linhas)
        return f'Nota nao encontrada: "{nota}". Use buscar ou listar_notas.'
    por_nome = {}
    for n in todas:
        por_nome.setdefault(n["nome"], n["rel"])
    saida = sorted(links_de(alvo["texto"]))
    entrada = sorted(n["rel"] for n in todas
                     if n is not alvo and alvo["nome"] in links_de(n["texto"]))
    linhas = [f"Nota: {alvo['rel']}", "", f"Saida ({len(saida)}):"]
    for alvo_link in saida:
        onde = por_nome.get(alvo_link)
        linhas.append(f"- [[{alvo_link}]]" + (f" → {onde}" if onde
                                              else " (sem arquivo no vault)"))
    linhas += ["", f"Backlinks ({len(entrada)}):"]
    linhas += [f"- {rel}" for rel in entrada]
    return "\n".join(linhas)


# ---------- escrita ----------

TIPOS = {"spec", "plano", "bug", "evolucao", "arquitetura", "adr", "analise", "mapa"}
STATUS = {"rascunho", "ativo", "resolvido", "obsoleto"}
PASTAS = {"spec": "Specs", "plano": "Specs", "bug": "Bugs", "evolucao": "Evolucoes",
          "arquitetura": "Arquitetura", "adr": "Arquitetura", "analise": "Analises"}
NOME_PROIBIDO_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SUBSTITUIDA_RE = re.compile(r"^Substituída por \[\[[^\]]*\]\]\.\n+")
PREFIXO_DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2} ")


def hoje():
    return time.strftime("%Y-%m-%d")


def nome_seguro(s):
    """Nome de arquivo/pasta valido em qualquer SO (acentos ficam)."""
    return " ".join(NOME_PROIBIDO_RE.sub("", str(s)).split()).rstrip(".")


def nome_de_nota(ref):
    return nome_seguro(re.sub(r"\.md$", "", str(ref).strip(), flags=re.I))


def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def escrever(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


def lista_tags(tags):
    if isinstance(tags, str):
        tags = tags.split(",")
    return [nome_seguro(t) for t in (tags or []) if str(t).strip()]


def bloco_frontmatter(projeto, tipo, status, data, tags):
    return (f"---\nprojeto: {projeto}\ntipo: {tipo}\nstatus: {status}\n"
            f"data: {data}\ntags: [{', '.join(lista_tags(tags))}]\n---\n")


def com_cabecalho(corpo, titulo, projeto):
    """Garante `# titulo` e o link do hub no corpo — nenhuma nota nasce orfa."""
    corpo = str(corpo).strip("\n")
    if not corpo.lstrip().startswith("# "):
        corpo = f"# {titulo}\n\n{corpo}"
    if f"[[{projeto}]]" not in corpo and f"[[{projeto}|" not in corpo:
        h1, _, resto = corpo.partition("\n")
        corpo = f"{h1}\n\nProjeto: [[{projeto}]]\n\n{resto.lstrip(chr(10))}".rstrip("\n")
    return corpo


def inserir_na_secao(texto, secao, linha, ordenar=False):
    """Poe a linha (bullet com wikilink) na secao `## secao`; cria a secao no fim
    se faltar. O wikilink ja esta na secao -> texto intacto."""
    alvo = WIKILINK_RE.search(linha).group(1).strip()
    linhas = texto.rstrip("\n").split("\n")
    ini = next((i for i, l in enumerate(linhas) if l.startswith("## ")
                and normalizar(l[3:]) == normalizar(secao)), None)
    if ini is None:
        return "\n".join(linhas + ["", f"## {secao}", "", linha]) + "\n"
    fim = next((i for i in range(ini + 1, len(linhas)) if linhas[i].startswith("#")),
               len(linhas))
    if any(f"[[{alvo}]]" in l or f"[[{alvo}|" in l for l in linhas[ini + 1:fim]):
        return texto
    bullets = [i for i in range(ini + 1, fim) if linhas[i].startswith("- ")]
    if not bullets:
        conteudo = [l for l in linhas[ini + 1:fim] if l.strip()]
        linhas[ini + 1:fim] = [""] + conteudo + [linha] + ([""] if fim < len(linhas) else [])
        return "\n".join(linhas) + "\n"
    pos = bullets[-1] + 1
    if ordenar:
        for i in bullets:
            m = WIKILINK_RE.search(linhas[i])
            if m and normalizar(m.group(1)) > normalizar(alvo):
                pos = i
                break
    linhas.insert(pos, linha)
    return "\n".join(linhas) + "\n"


def git(*args):
    r = subprocess.run(["git", "-C", VAULT, *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def vault_com_git():
    if SEM_GIT or not shutil.which("git"):
        return False
    return git("rev-parse", "--is-inside-work-tree")[0] == 0


def puxar():
    """Antes de escrever: outras maquinas e sessoes tambem gravam no vault."""
    if vault_com_git():
        git("pull", "--rebase", "--autostash")  # offline ou sem upstream: segue local


def sincronizar(mensagem):
    """commit -> pull --rebase -> push. Falha vira texto; a nota ja esta gravada."""
    if not vault_com_git():
        return "sem git (vault nao e repositorio, ou --sem-git)"
    git("add", "-A")
    rc, saida = git("commit", "-q", "-m", mensagem)
    if rc != 0:
        return "nada a commitar" if "nothing to commit" in saida else f"commit falhou: {saida[-300:]}"
    if not git("remote")[1]:
        return "commit local (vault sem remoto)"
    rc, saida = git("pull", "--rebase", "--autostash")
    if rc != 0:
        git("rebase", "--abort")
        return f"commit local; pull --rebase falhou: {saida[-300:]}"
    rc, saida = git("push")
    return "commit + push ok" if rc == 0 else f"commit local; push falhou: {saida[-300:]}"


def garantir_home():
    caminho = os.path.join(VAULT, "Home.md")
    if not os.path.exists(caminho):
        escrever(caminho, bloco_frontmatter("vault", "hub", "ativo", hoje(), ["hub"])
                 + "\n# Home\n\nVault de documentação de todos os projetos. "
                   "Um hub por projeto abaixo.\n\n## Projetos\n")


def garantir_hub(projeto, descricao, repo):
    """Hub existente sempre ganha. Projeto novo exige descricao (1 linha)."""
    caminho = os.path.join(VAULT, projeto, projeto + ".md")
    if os.path.exists(caminho):
        return False
    descricao = " ".join(str(descricao or "").split()).rstrip(".")
    if not descricao:
        raise ErroUso(f'projeto "{projeto}" nao existe no vault. E novo mesmo? Confira com '
                      "visao_geral (hub existente sempre ganha) e, se for novo, passe "
                      "descricao_projeto (1 linha) e repo (caminho local do repositorio).")
    corpo = f"\n# {projeto}\n\n{descricao}. Hub global: [[Home]].\n"
    if repo:
        corpo += f"Repo: {repo}\n"
    escrever(caminho, bloco_frontmatter(projeto, "hub", "ativo", hoje(), ["hub"]) + corpo)
    garantir_home()
    home = os.path.join(VAULT, "Home.md")
    escrever(home, inserir_na_secao(ler(home), "Projetos",
                                    f"- [[{projeto}]] — {descricao}", ordenar=True))
    return True


def salvar_nota(projeto="", tipo="", titulo="", corpo="", resumo="", status="ativo",
                tags=None, data=None, artefato=None, descricao_projeto=None, repo=None,
                sobrescrever=False, arquivos=None):
    projeto, titulo = nome_seguro(projeto), nome_seguro(titulo)
    tipo, status = normalizar(tipo), normalizar(status or "ativo")
    resumo = " ".join(str(resumo or "").split())
    if not projeto or not titulo or not str(corpo).strip():
        raise ErroUso("projeto, titulo e corpo sao obrigatorios")
    if tipo not in TIPOS:
        raise ErroUso(f"tipo invalido: {tipo!r}. Use: " + ", ".join(sorted(TIPOS)))
    if status not in STATUS:
        raise ErroUso(f"status invalido: {status!r}. Use: " + ", ".join(sorted(STATUS)))
    data = str(data or hoje())
    if not DATA_RE.fullmatch(data):
        raise ErroUso("data deve ser YYYY-MM-DD")
    if tipo == "mapa":
        nome, pasta, secao, sobrescrever = f"Mapa do Codigo {projeto}", "", "Mapa", True
        resumo = resumo or "mapa curado do codigo (graphify)"
    else:
        if not resumo:
            raise ErroUso("resumo (1 linha; vira a entrada no hub) e obrigatorio")
        nome, pasta, secao = f"{data} {titulo}", PASTAS[tipo], PASTAS[tipo]
        if artefato:
            if pasta != "Specs":
                raise ErroUso("artefato (ticket) so vale para tipo spec ou plano")
            pasta = f"Specs/Tickets - {nome_de_nota(artefato)}"
    rel = "/".join(p for p in (projeto, pasta, nome + ".md") if p)
    caminho = os.path.join(VAULT, *rel.split("/"))
    puxar()
    if os.path.exists(caminho) and not sobrescrever:
        raise ErroUso(f"ja existe: {rel}. Mudar o conteudo: atualizar_nota; "
                      "regravar do zero: sobrescrever=true.")
    todas = notas()
    hub_novo = garantir_hub(projeto, descricao_projeto, repo)
    aviso = None
    if arquivos:
        lista = arquivos.split(",") if isinstance(arquivos, str) else list(arquivos)
        try:
            componentes, aviso = componentes_tocados(projeto, lista, repo)
            corpo = str(corpo).rstrip("\n") + "\n\n" + componentes
        except ErroUso as e:
            aviso = f"Componentes: grafo indisponivel ({e})"
    texto = (bloco_frontmatter(projeto, tipo, status, data, tags) + "\n"
             + com_cabecalho(corpo, titulo, projeto) + "\n")
    escrever(caminho, texto)
    hub = os.path.join(VAULT, projeto, projeto + ".md")
    escrever(hub, inserir_na_secao(ler(hub), secao, f"- [[{nome}]] — {resumo}"))
    linhas = [f"Salva: {rel}",
              "Hub: " + ("criado e registrado no Home" if hub_novo else "entrada adicionada")
              + f" ({projeto}/{projeto}.md)"]
    if hub_novo:
        np = normalizar(projeto)
        parecidos = sorted({n["projeto"] for n in todas if n["fm"].get("tipo") == "hub"
                            and n["projeto"] and n["projeto"] != projeto
                            and (np in normalizar(n["projeto"]) or normalizar(n["projeto"]) in np)})
        if parecidos:
            linhas.append("Aviso: ja existiam hubs parecidos — confira se nao era um deles: "
                          + ", ".join(parecidos))
    nomes = {n["nome"] for n in notas()}
    quebrados = sorted(l for l in links_de(texto) if l not in nomes)
    if quebrados:
        linhas.append("Wikilinks sem nota no vault (corrija ou crie a nota): "
                      + ", ".join(f"[[{l}]]" for l in quebrados))
    if aviso:
        linhas.append(aviso)
    linhas.append("Git: " + sincronizar(f"{projeto}: {nome if tipo == 'mapa' else titulo}"))
    return "\n".join(linhas)


def atualizar_nota(nota="", corpo=None, status=None, tags=None, sucessora=None, resumo=None):
    if corpo is None and status is None and tags is None and not sucessora and not resumo:
        raise ErroUso("informe ao menos um de: corpo, status, tags, sucessora, resumo")
    puxar()
    todas = notas()
    alvo, candidatos = achar(nota, todas)
    if not alvo:
        if candidatos:
            raise ErroUso(f'mais de uma nota bate com "{nota}" — repita com o caminho: '
                          + "; ".join(n["rel"] for n in candidatos[:10]))
        raise ErroUso(f'nota nao encontrada: "{nota}". Use buscar ou listar_notas para achar.')
    if alvo["fm"].get("tipo") == "hub":
        raise ErroUso("hub e indice mantido pelo servidor: grave notas (salvar_nota) ou "
                      "mude o resumo de uma nota (atualizar_nota resumo=...)")
    texto = alvo["texto"].replace("\r\n", "\n")
    fim = texto.find("\n---", 3) if texto.startswith("---") else -1
    if fim == -1:
        raise ErroUso(f"{alvo['rel']} nao tem frontmatter; regrave com salvar_nota "
                      "(sobrescrever=true)")
    cabeca, resto = texto[:fim + 4], texto[fim + 4:]
    projeto = alvo["projeto"] or alvo["fm"].get("projeto", "")
    mudou = []
    if corpo is not None:
        resto = "\n" + com_cabecalho(corpo, PREFIXO_DATA_RE.sub("", alvo["nome"]), projeto) + "\n"
        mudou.append("corpo")
    if sucessora:
        alvo_suc, cands_suc = achar(sucessora, todas)   # mesma resolucao da nota-alvo
        if not alvo_suc and cands_suc:
            raise ErroUso(f'mais de uma nota bate com a sucessora "{sucessora}" — repita com o '
                          "caminho: " + "; ".join(n["rel"] for n in cands_suc[:5]))
        if not alvo_suc:
            raise ErroUso(f"sucessora nao existe no vault: {sucessora}. Crie-a antes (salvar_nota).")
        if alvo_suc["rel"] == alvo["rel"]:
            raise ErroUso(f"sucessora e a propria nota ({alvo['rel']}); passe a nota que a substitui")
        nome_suc = alvo_suc["nome"]
        # uma sucessora por vez: a linha anterior sai, a nova entra no topo do corpo
        resto = SUBSTITUIDA_RE.sub("", resto.lstrip("\n"), count=1)
        resto = f"\nSubstituída por [[{nome_suc}]].\n" + resto.lstrip("\n")
        status = status or "obsoleto"
        mudou.append(f"sucessora=[[{nome_suc}]]")
    if status is not None:
        status = normalizar(status)
        if status not in STATUS:
            raise ErroUso(f"status invalido: {status!r}. Use: " + ", ".join(sorted(STATUS)))
        cabeca = re.sub(r"(?m)^status:.*$", f"status: {status}", cabeca, count=1)
        mudou.append(f"status={status}")
    if tags is not None:
        linha = f"tags: [{', '.join(lista_tags(tags))}]"
        if re.search(r"(?m)^tags:", cabeca):
            cabeca = re.sub(r"(?m)^tags:.*$", linha, cabeca, count=1)
        else:
            cabeca = cabeca.replace("\n---", f"\n{linha}\n---", 1)
        mudou.append("tags")
    escrever(os.path.join(VAULT, *alvo["rel"].split("/")), cabeca + resto)
    if resumo:
        hub = os.path.join(VAULT, projeto, projeto + ".md")
        padrao = re.compile(r"(?m)^(- \[\[" + re.escape(alvo["nome"]) + r"(?:\|[^\]]*)?\]\]).*$")
        resumo = " ".join(str(resumo).split())
        novo, n = (padrao.subn(lambda m: f"{m.group(1)} — {resumo}", ler(hub))
                   if os.path.exists(hub) else ("", 0))
        if n:
            escrever(hub, novo)
            mudou.append("resumo no hub")
        else:
            mudou.append("resumo ignorado: a nota nao esta listada no hub")
    return (f"Atualizada: {alvo['rel']} ({', '.join(mudou)})\nGit: "
            + sincronizar(f"{projeto}: {alvo['nome']}"))


# ---------- graphify (grafo de codigo do repo, via ponteiro Repo: do hub) ----------

REPO_RE = re.compile(r"(?m)^Repo:\s*(.+?)\s*$")
CAMINHO_RE = re.compile(r"[A-Za-z]:[\\/][^\s`*|]+|/[^\s`*|]+|~[^\s`*|]*")


def caminho_da_linha(linha):
    """Hub escrito a mao traz coisas como `Repo: **`D:\\x`** no master (Windows)`:
    o caminho e so o primeiro trecho que parece caminho."""
    m = CAMINHO_RE.search(linha)
    return m.group(0).rstrip(".,;)") if m else linha.strip("`* ")
TETO_SAIDA = 8000


def git_em(pasta, *args):
    r = subprocess.run(["git", "-C", pasta, *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def registrar_repo(texto_hub, repo):
    """Poe `Repo: <caminho>` no fim do paragrafo de descricao do hub."""
    linhas = texto_hub.rstrip("\n").split("\n")
    pos = len(linhas)
    h1 = next((i for i, l in enumerate(linhas) if l.startswith("# ")), None)
    if h1 is not None:
        i = h1 + 1
        while i < len(linhas) and not linhas[i].strip():
            i += 1
        while i < len(linhas) and linhas[i].strip() and not linhas[i].startswith("#"):
            i += 1
        pos = i
    linhas.insert(pos, f"Repo: {repo}")
    return "\n".join(linhas) + "\n"


def repo_do_projeto(projeto, repo=None):
    """(caminho do repo, registrado_no_hub). Parametro > linha Repo: do hub > erro."""
    hub = os.path.join(VAULT, projeto, projeto + ".md")
    if not os.path.exists(hub):
        raise ErroUso(f'projeto "{projeto}" nao tem hub no vault (visao_geral lista os que existem)')
    texto = ler(hub)
    m = REPO_RE.search(texto)
    atual = caminho_da_linha(m.group(1)) if m else None
    registrado = False
    if repo:
        repo = os.path.abspath(os.path.expanduser(str(repo)))
        if not m:
            escrever(hub, registrar_repo(texto, repo))
            registrado = True
        elif os.path.normcase(atual) != os.path.normcase(repo):
            # o repositorio mudou de pasta: so o caminho muda, o resto da linha fica
            escrever(hub, texto.replace(m.group(0), m.group(0).replace(atual, repo, 1), 1))
            registrado = True
    elif m:
        repo = atual
    else:
        raise ErroUso(f"hub de {projeto} sem linha `Repo:`; passe repo=<caminho do repositorio>")
    if not os.path.isdir(repo):
        raise ErroUso(f"repo nao esta nesta maquina: {repo}")
    return repo, registrado


def grafo_do_projeto(projeto, repo=None):
    """(repo, registrado, grafo, pasta do graphify-out)."""
    repo, registrado = repo_do_projeto(projeto, repo)
    pasta = os.path.join(repo, "graphify-out")
    caminho = os.path.join(pasta, "graph.json")
    if not os.path.exists(caminho):
        raise ErroUso(f"sem grafo em {pasta}: rode /graphify-ai no repo "
                      "(graphify-out fica no repo, no .gitignore)")
    with open(caminho, encoding="utf-8") as f:
        return repo, registrado, json.load(f), pasta


def frescor(repo, g):
    commit = str(g.get("built_at_commit") or "")
    curto = commit[:7] or "?"
    if not shutil.which("git") or git_em(repo, "rev-parse", "--is-inside-work-tree")[0] != 0:
        return f"Commit do grafo: {curto} | sem git"
    head = git_em(repo, "rev-parse", "HEAD")[1][:7]
    if not commit:
        estado = "commit do grafo desconhecido"
    elif commit[:7] == head:
        estado = "atualizado"
    else:
        rc, n = git_em(repo, "rev-list", "--count", f"{commit}..HEAD")
        estado = f"atrasado {n} commit(s)" if rc == 0 else "atrasado (commit do grafo fora do historico)"
    return f"Commit do grafo: {curto} | HEAD: {head} | {estado}"


def rotulos_comunidades(pasta):
    p = os.path.join(pasta, ".graphify_labels.json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    if isinstance(d, dict) and isinstance(d.get("labels"), dict):
        d = d["labels"]
    return {str(k): str(v) for k, v in d.items()} if isinstance(d, dict) else {}


def analisar_grafo(g, pasta):
    """(nos por id, grau, [(rotulo, ids por grau desc)] por tamanho desc, god nodes, n arestas)."""
    nos = {n["id"]: n for n in g.get("nodes", []) if isinstance(n, dict) and "id" in n}
    arestas = g.get("links") or g.get("edges") or []
    grau = Counter()
    for e in arestas:
        grau[e.get("source")] += 1
        grau[e.get("target")] += 1
    rotulos = rotulos_comunidades(pasta)
    por_comunidade = defaultdict(list)
    for nid, n in nos.items():
        por_comunidade[str(n.get("community", "?"))].append(nid)
    comunidades = []
    for cid, ids in por_comunidade.items():
        ids.sort(key=lambda i: -grau[i])
        comunidades.append((rotulos.get(cid, f"comunidade {cid}"), ids))
    comunidades.sort(key=lambda c: -len(c[1]))
    god = sorted(nos, key=lambda i: -grau[i])[:10]
    return nos, grau, comunidades, god, len(arestas)


def secoes_do_report(pasta):
    """Secoes do GRAPH_REPORT.md sobre conexoes e perguntas, ate 30 linhas cada."""
    p = os.path.join(pasta, "GRAPH_REPORT.md")
    if not os.path.exists(p):
        return ""
    saida, pegar, n = [], False, 0
    for l in ler(p).split("\n"):
        if l.startswith("#"):
            t = normalizar(l)
            pegar = any(k in t for k in ("connection", "conex", "question", "pergunta"))
            n = 0
            if pegar:
                saida.append(l.lstrip("#").strip() + ":")
            continue
        if pegar and l.strip() and n < 30:
            saida.append(l)
            n += 1
    return "\n".join(saida)


def resumo_grafo(g, pasta, max_comunidades=20):
    """(linhas das maiores comunidades, linhas de god nodes, texto do report,
    n nos, n arestas, n comunidades). Projeto grande tem centenas de comunidades:
    listar todas estourava o teto da saida antes dos god nodes."""
    nos, grau, comunidades, god, n_arestas = analisar_grafo(g, pasta)

    def rot(i):
        return str(nos[i].get("label") or i)

    mostradas = comunidades if max_comunidades is None else comunidades[:max_comunidades]
    resto = [] if max_comunidades is None else comunidades[max_comunidades:]
    com = [f"- {nome} — {len(ids)} nós: " + ", ".join(rot(i) for i in ids[:3])
           for nome, ids in mostradas]
    if resto:
        com.append(f"- … e mais {len(resto)} comunidades menores "
                   f"({sum(len(ids) for _, ids in resto)} nós)")
    gods = [f"- {rot(i)} ({nos[i].get('source_file', '?')}) — grau {grau[i]}" for i in god]
    return com, gods, secoes_do_report(pasta), len(nos), n_arestas, len(comunidades)


def mapa_codigo(projeto="", repo=None):
    repo, registrado, g, pasta = grafo_do_projeto(projeto, repo)
    com, gods, rep, n_nos, n_arestas, n_com = resumo_grafo(g, pasta)
    linhas = [f"Grafo: {os.path.join(pasta, 'graph.json')} — {n_nos} nós, {n_arestas} arestas",
              frescor(repo, g), "God nodes (10 por grau):"] + gods + \
             [f"Comunidades ({n_com}, as maiores primeiro):"] + com
    if rep:
        linhas += ["Do GRAPH_REPORT.md:", rep]
    saida = "\n".join(linhas)
    if len(saida) > TETO_SAIDA:
        saida = saida[:TETO_SAIDA] + f"\n… (saída cortada em {TETO_SAIDA} caracteres)"
    if registrado:  # depois do corte: o aviso de que o hub mudou nunca some
        saida += "\nHub: linha Repo registrada. Git: " + sincronizar(f"{projeto}: Repo registrado no hub")
    return saida


def componentes_tocados(projeto, arquivos, repo=None):
    """('## Componentes tocados' pronta, linha-resumo) a partir do grafo do repo."""
    repo, _, g, pasta = grafo_do_projeto(projeto, repo)
    nos, grau, comunidades, _, _ = analisar_grafo(g, pasta)
    rotulo_de = {i: nome for nome, ids in comunidades for i in ids}
    raiz = repo.replace("\\", "/").rstrip("/") + "/"
    achados, sem_no, vistos = defaultdict(list), [], set()
    for arq in arquivos:
        a = str(arq).replace("\\", "/").strip()
        if a.startswith("./"):
            a = a[2:]
        if a.startswith(raiz):
            a = a[len(raiz):]
        ids = []
        for i, n in nos.items():
            sf = str(n.get("source_file") or "").replace("\\", "/")
            if sf and (sf == a or sf.endswith("/" + a) or a.endswith("/" + sf)):
                ids.append(i)
        if not ids:
            sem_no.append(a)
            continue
        # o mesmo arquivo pode vir duas vezes (a.py e ./a.py): cada no conta uma vez
        for i in sorted(ids, key=lambda i: -grau[i]):
            if i not in vistos:
                vistos.add(i)
                achados[rotulo_de.get(i, "?")].append(str(nos[i].get("label") or i))
    total = len(vistos)
    # a secao e relida em toda leitura da nota: 6 comunidades, 5 rotulos cada
    ordenadas = sorted(achados.items(), key=lambda kv: -len(kv[1]))
    linhas = ["## Componentes tocados", ""]
    for nome, labels in ordenadas[:6]:
        extra = f" (+{len(labels) - 5})" if len(labels) > 5 else ""
        linhas.append(f"- {nome}: " + ", ".join(labels[:5]) + extra + f" ({len(labels)} nós)")
    if len(ordenadas) > 6:
        linhas.append(f"- … e mais {len(ordenadas) - 6} comunidades "
                      f"({sum(len(l) for _, l in ordenadas[6:])} nós)")
    if sem_no:
        linhas.append("- sem nó no grafo: " + ", ".join(sem_no))
    if os.path.exists(os.path.join(VAULT, projeto, f"Mapa do Codigo {projeto}.md")):
        linhas.append(f"Mapa: [[Mapa do Codigo {projeto}]]")
    resumo = f"Componentes: {total} nós em {len(achados)} comunidades; {len(sem_no)} arquivo(s) sem nó"
    return "\n".join(linhas), resumo


LEITURA_RE = re.compile(r"(?ms)^## Leitura curada\s*\n(.*?)(?=^## |\Z)")


def gerar_mapa(projeto="", leitura=None, repo=None):
    repo, _, g, pasta = grafo_do_projeto(projeto, repo)
    nome = f"Mapa do Codigo {projeto}"
    existente = os.path.join(VAULT, projeto, nome + ".md")
    if leitura is None and os.path.exists(existente):
        m = LEITURA_RE.search(ler(existente))
        leitura = m.group(1) if m else None
    leitura = (leitura or "").strip() or "(ainda sem leitura curada — passe leitura em gerar_mapa)"
    com, gods, rep, _, _, n_com = resumo_grafo(g, pasta, max_comunidades=None)  # a nota e o indice: completa
    commit = str(g.get("built_at_commit") or "")[:7] or "?"
    corpo = [f"# {nome}", "",
             f"Projeto: [[{projeto}]]. Gerado do graphify-out em {hoje()} (commit {commit}).", "",
             "## Leitura curada", "", leitura, "", "## God nodes", ""] + gods + \
            ["", f"## Comunidades ({n_com})", ""] + com
    if rep:
        corpo += ["", "## Conexões e perguntas (GRAPH_REPORT)", "", rep]
    return salvar_nota(projeto=projeto, tipo="mapa", titulo=nome, corpo="\n".join(corpo), repo=repo)


def consultar_codigo(projeto="", pergunta=None, explicar=None, caminho=None, repo=None):
    if sum(1 for x in (pergunta, explicar, caminho) if x) != 1:
        raise ErroUso("informe exatamente um de: pergunta, explicar, caminho=[A, B]")
    exe = shutil.which("graphify")
    if not exe:
        raise ErroUso("graphify nao instalado: pip install graphifyy")
    repo, registrado, _, pasta = grafo_do_projeto(projeto, repo)
    grafo = os.path.join(pasta, "graph.json")
    if pergunta:
        cmd = [exe, "query", str(pergunta), "--graph", grafo, "--budget", "2000"]
    elif explicar:
        cmd = [exe, "explain", str(explicar), "--graph", grafo]
    else:
        if not isinstance(caminho, list) or len(caminho) != 2:
            raise ErroUso("caminho deve ser uma lista com dois rotulos: [A, B]")
        cmd = [exe, "path", str(caminho[0]), str(caminho[1]), "--graph", grafo]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60, cwd=repo)
    except subprocess.TimeoutExpired:
        raise ErroUso("graphify demorou mais de 60 s")
    if r.returncode != 0:
        raise ErroUso(f"graphify falhou: {(r.stderr or r.stdout).strip()[-500:]}")
    saida = r.stdout.strip() or "(sem resultado)"
    if registrado:
        saida += "\nHub: linha Repo registrada. Git: " + sincronizar(f"{projeto}: Repo registrado no hub")
    return saida[:TETO_SAIDA]


# ---------- definicao das ferramentas ----------

def esquema(props, *obrigatorios):
    return {"type": "object", "properties": props,
            "required": list(obrigatorios), "additionalProperties": False}


P_PROJETO = {"type": "string",
             "description": "Filtra por projeto (nome da pasta no vault)."}
P_TIPO = {"type": "string",
          "description": "Filtra por tipo: spec, plano, bug, evolucao, "
                         "arquitetura, adr, analise, mapa ou hub."}
P_STATUS = {"type": "string",
            "description": "Filtra por status: ativo, rascunho, resolvido "
                           "ou obsoleto."}
P_NOTA = {"type": "string",
          "description": "Caminho relativo ao vault (projeto/Specs/2026-01-02 "
                         "X.md) ou nome da nota como em wikilink (2026-01-02 X)."}

P_PROJ = {"type": "string", "description": "Nome do projeto (pasta no vault)."}
P_REPO = {"type": "string",
          "description": "Caminho local do repositorio; so se o hub nao tiver a linha "
                         "`Repo:` (fica registrado nele)."}

FERRAMENTAS = [
    {"name": "visao_geral",
     "description": "Panorama do vault de documentacao: projetos, contagem de "
                    "notas por tipo e notas recentes. Bom primeiro passo.",
     "inputSchema": esquema({}),
     "fn": visao_geral},
    {"name": "buscar",
     "description": "Busca full-text nas notas do vault, ignorando acentos e "
                    "maiusculas; varios termos separados por espaco = todos "
                    "precisam aparecer. Retorna caminho, metadados e trecho.",
     "inputSchema": esquema({
         "consulta": {"type": "string",
                      "description": "Termos de busca (obrigatorio)."},
         "projeto": P_PROJETO, "tipo": P_TIPO, "status": P_STATUS,
         "limite": {"type": "integer",
                    "description": "Maximo de resultados (padrao 10, teto 30)."},
     }, "consulta"),
     "fn": buscar},
    {"name": "listar_notas",
     "description": "Lista notas (caminho + frontmatter, sem conteudo), mais "
                    "recentes primeiro. Filtros opcionais projeto/tipo/status.",
     "inputSchema": esquema({
         "projeto": P_PROJETO, "tipo": P_TIPO, "status": P_STATUS,
         "limite": {"type": "integer",
                    "description": "Maximo de notas (padrao 20, teto 100)."},
     }),
     "fn": listar_notas},
    {"name": "ler_nota",
     "description": "Le o conteudo integral de uma nota do vault.",
     "inputSchema": esquema({"nota": P_NOTA}, "nota"),
     "fn": ler_nota},
    {"name": "conexoes",
     "description": "Wikilinks de saida e backlinks de uma nota — navegacao "
                    "pelo grafo do vault.",
     "inputSchema": esquema({"nota": P_NOTA}, "nota"),
     "fn": conexoes},
    {"name": "salvar_nota",
     "description": "Cria uma nota nova no vault com tudo que a convencao exige: "
                    "pasta por tipo, nome `YYYY-MM-DD titulo`, frontmatter, `# titulo` e "
                    "link do hub no corpo, entrada no hub (hub e Home criados se o "
                    "projeto for novo) e commit+push se o vault for git. Ticket de um "
                    "artefato: passe `artefato`. tipo=mapa regrava `Mapa do Codigo "
                    "<projeto>` na raiz do projeto. Nota que ja existe: atualizar_nota.",
     "inputSchema": esquema({
         "projeto": {"type": "string",
                     "description": "Nome do projeto = pasta do repo git (minusculo, "
                                    "sem acento). Hub existente sempre ganha."},
         "tipo": {"type": "string",
                  "description": "spec | plano | bug | evolucao | arquitetura | adr | "
                                 "analise | mapa"},
         "titulo": {"type": "string", "description": "Titulo curto; vira o nome do "
                                                     "arquivo (ignorado para mapa)."},
         "corpo": {"type": "string",
                   "description": "Markdown da nota. `# titulo` e `Projeto: [[projeto]]` "
                                  "sao adicionados se faltarem. Linke notas relacionadas "
                                  "por [[nome da nota]]."},
         "resumo": {"type": "string",
                    "description": "1 linha: vira a entrada da nota no hub (obrigatorio, "
                                   "exceto mapa)."},
         "status": {"type": "string",
                    "description": "rascunho | ativo (padrao) | resolvido | obsoleto"},
         "tags": {"type": "array", "items": {"type": "string"},
                  "description": "1-3 tags kebab-case sem acento (opcional)."},
         "data": {"type": "string",
                  "description": "YYYY-MM-DD (padrao: hoje). Migracao: data do 1o commit."},
         "artefato": {"type": "string",
                      "description": "Nome da nota (sem .md) que originou este ticket: "
                                     "grava em Specs/Tickets - <artefato>/."},
         "descricao_projeto": {"type": "string",
                               "description": "So para projeto NOVO: 1 linha para o hub "
                                              "e o Home."},
         "repo": {"type": "string",
                  "description": "Caminho local do repositorio: usado ao criar o hub e como "
                                 "ponteiro do graphify (registrado no hub se faltar)."},
         "sobrescrever": {"type": "boolean",
                          "description": "Regrava se a nota ja existir (padrao false)."},
         "arquivos": {"type": "array", "items": {"type": "string"},
                      "description": "Caminhos (relativos ao repo) tocados pela leva: o "
                                     "servidor anexa a secao Componentes tocados a partir "
                                     "do grafo do graphify (evolucao, bug, spec de mudanca)."},
     }, "projeto", "tipo", "titulo", "corpo"),
     "fn": salvar_nota},
    {"name": "atualizar_nota",
     "description": "Altera uma nota existente, in-place: `corpo` (substitui o texto "
                    "apos o frontmatter), `status`, `tags`, `sucessora` (marca obsoleta e "
                    "linka a nota que a substitui) e `resumo` (linha da nota no hub). "
                    "Commit+push se o vault for git.",
     "inputSchema": esquema({
         "nota": P_NOTA,
         "corpo": {"type": "string", "description": "Novo corpo completo em markdown."},
         "status": {"type": "string",
                    "description": "rascunho | ativo | resolvido | obsoleto"},
         "tags": {"type": "array", "items": {"type": "string"}},
         "sucessora": {"type": "string",
                       "description": "Nome da nota que substitui esta (sem .md)."},
         "resumo": {"type": "string", "description": "Nova linha de resumo no hub."},
     }, "nota"),
     "fn": atualizar_nota},
    {"name": "mapa_codigo",
     "description": "Mapa do codigo do projeto a partir do graphify-out do repo (ponteiro "
                    "Repo: do hub): frescor do grafo, god nodes, as 20 maiores comunidades e "
                    "destaques do GRAPH_REPORT. Leia antes de mexer no codigo.",
     "inputSchema": esquema({"projeto": P_PROJ, "repo": P_REPO}, "projeto"),
     "fn": mapa_codigo},
    {"name": "consultar_codigo",
     "description": "Pergunta de arquitetura ao grafo do graphify (CLI local): `pergunta` "
                    "livre, `explicar` um no, ou `caminho` entre dois nos. Exatamente um.",
     "inputSchema": esquema({
         "projeto": P_PROJ,
         "pergunta": {"type": "string", "description": "Pergunta livre (BFS no grafo)."},
         "explicar": {"type": "string", "description": "Rotulo do no a explicar."},
         "caminho": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2,
                     "description": "Dois rotulos: caminho mais curto de A a B."},
         "repo": P_REPO,
     }, "projeto"),
     "fn": consultar_codigo},
    {"name": "gerar_mapa",
     "description": "Regrava a nota `Mapa do Codigo <projeto>` a partir do graphify-out "
                    "(god nodes, todas as comunidades, GRAPH_REPORT) preservando a secao Leitura "
                    "curada; passe `leitura` para atualiza-la. Chame apos cada rodada do graphify.",
     "inputSchema": esquema({
         "projeto": P_PROJ,
         "leitura": {"type": "string", "description": "Sua leitura curada (dominios, o que "
                                                      "vale saber, lacunas)."},
         "repo": P_REPO,
     }, "projeto"),
     "fn": gerar_mapa},
]
MAPA = {f["name"]: f for f in FERRAMENTAS}


# ---------- instalacao ----------

def instalar(vault_explicito):
    """Registra este servidor no Claude Code (`claude mcp add`, escopo user)."""
    if VAULT is None:
        return ("vault nao encontrado: defina OBSIDIAN_VAULT ou passe "
                "--instalar --vault <pasta de projetos do vault>")
    claude = shutil.which("claude")
    if not claude:
        return "`claude` nao esta no PATH: instale o Claude Code antes"
    servidor = [sys.executable, os.path.abspath(__file__)]
    if vault_explicito:
        servidor += ["--vault", VAULT]
    if SEM_GIT:
        servidor.append("--sem-git")
    # apaga registro anterior para o comando poder ser repetido
    subprocess.run([claude, "mcp", "remove", "-s", "user", "vault-docs"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    r = subprocess.run([claude, "mcp", "add", "-s", "user", "vault-docs", "--"]
                       + servidor)
    if r.returncode != 0:
        return r.returncode
    print("vault-docs registrado (escopo user). Reinicie o Claude Code e "
          "confira com `claude mcp list`.")
    return 0


# ---------- protocolo (JSON-RPC 2.0 sobre stdio) ----------

def responder(id_, resultado=None, erro=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    if erro is not None:
        msg["error"] = erro
    else:
        msg["result"] = resultado
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def chamar_ferramenta(id_, params):
    nome = params.get("name")
    fer = MAPA.get(nome)
    if fer is None:
        responder(id_, erro={"code": -32602,
                             "message": f"ferramenta desconhecida: {nome}"})
        return
    if VAULT is None:
        texto, falhou = ERRO_VAULT, True
    else:
        try:
            texto, falhou = fer["fn"](**(params.get("arguments") or {})), False
        except ErroUso as e:
            texto, falhou = str(e), True
        except TypeError as e:
            texto, falhou = f"argumentos invalidos: {e}", True
        except Exception as e:  # nunca derrubar o servidor por uma chamada
            texto, falhou = f"erro ao executar {nome}: {e}", True
    responder(id_, {"content": [{"type": "text", "text": texto}],
                    "isError": falhou})


def atender(msg):
    metodo, id_, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if metodo == "initialize":
        versao = params.get("protocolVersion")
        responder(id_, {
            "protocolVersion": versao if versao in PROTOCOLOS else PROTOCOLO_PADRAO,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "obsidian-docs", "version": "2.0.0"},
            "instructions": INSTRUCOES,
        })
    elif metodo == "ping":
        responder(id_, {})
    elif metodo == "tools/list":
        responder(id_, {"tools": [
            {k: f[k] for k in ("name", "description", "inputSchema")}
            for f in FERRAMENTAS]})
    elif metodo == "tools/call":
        chamar_ferramenta(id_, params)
    elif id_ is None:
        pass  # notificacoes (initialized, cancelled, ...) nao tem resposta
    else:
        responder(id_, erro={"code": -32601,
                             "message": f"metodo desconhecido: {metodo}"})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", default=None,
                    help="pasta de projetos do vault (senao usa OBSIDIAN_VAULT)")
    ap.add_argument("--instalar", action="store_true",
                    help="registra este servidor no Claude Code (escopo user) e sai")
    ap.add_argument("--sem-git", action="store_true",
                    help="nunca commitar/empurrar o vault, mesmo sendo repositorio git")
    args = ap.parse_args()

    global VAULT, SEM_GIT
    SEM_GIT = args.sem_git
    caminho = args.vault or os.environ.get("OBSIDIAN_VAULT")
    if caminho:
        caminho = os.path.abspath(os.path.expanduser(caminho))
    if caminho and os.path.isdir(caminho):
        VAULT = caminho
    else:
        origem = caminho or "OBSIDIAN_VAULT nao definido"
        print(f"servidor_vault: vault indisponivel ({origem}); "
              "ferramentas vao instruir a configuracao", file=sys.stderr)

    if args.instalar:
        sys.exit(instalar(bool(args.vault)))

    # stdout transporta o protocolo: UTF-8 e \n mesmo no Windows
    for fluxo in (sys.stdin, sys.stdout):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", newline="\n")

    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        try:
            msg = json.loads(linha)
        except ValueError:
            responder(None, erro={"code": -32700, "message": "JSON invalido"})
            continue
        try:
            atender(msg)
        except Exception as e:  # erro interno nao pode matar o processo
            responder(msg.get("id"), erro={"code": -32603, "message": str(e)})


if __name__ == "__main__":
    main()
