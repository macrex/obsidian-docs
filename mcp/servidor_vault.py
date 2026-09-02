#!/usr/bin/env python3
"""Servidor MCP do vault Obsidian: busca e leitura das notas para LLMs.

Zero dependencias: o protocolo MCP (JSON-RPC 2.0 sobre stdio, uma mensagem
por linha) e implementado so com a biblioteca padrao (Python 3.9+). Tudo e
filesystem — o Obsidian nao precisa estar aberto.

Registro no Claude Code (uma vez, vale para qualquer projeto):

  claude mcp add --scope user vault-docs -- python3 <repo>/mcp/servidor_vault.py

Windows: troque `python3` por `python`. O caminho do vault vem de
`OBSIDIAN_VAULT` (a pasta de projetos, a mesma das skills) ou de
`--vault <caminho>` no fim do comando. Caminho nunca e inventado.

Ferramentas (todas somente leitura):
  visao_geral    panorama: projetos, contagem por tipo, notas recentes
  buscar         full-text sem acento/caixa, filtros projeto/tipo/status
  listar_notas   metadados das notas, mais recentes primeiro
  ler_nota       conteudo integral (caminho relativo ou nome de wikilink)
  conexoes       wikilinks de saida e backlinks (navegacao no grafo)
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict

PROTOCOLOS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
PROTOCOLO_PADRAO = "2025-06-18"
IGNORAR = {".obsidian", ".scripts", ".git"}
# [[alvo]] e [[alvo|texto]]; blocos e trechos de codigo nao contam como link
WIKILINK_RE = re.compile(r"\[\[([^\]\[|#]+)")
CODEBLOCK_RE = re.compile(r"```.*?```", re.S)
INLINECODE_RE = re.compile(r"`[^`\n]+`")
DATA_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

VAULT = None  # resolvido em main()

INSTRUCOES = (
    "Vault Obsidian com a documentacao dos projetos (specs, planos, ADRs, bugs, "
    "evolucoes, analises). Estrutura: Home.md -> <projeto>/<projeto>.md (hub) -> "
    "Specs/, Arquitetura/, Bugs/, Evolucoes/, Analises/. Comece com visao_geral "
    "ou buscar; ler_nota traz o conteudo; conexoes navega o grafo de wikilinks."
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
                texto = open(caminho, encoding="utf-8").read()
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
]
MAPA = {f["name"]: f for f in FERRAMENTAS}


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
            "serverInfo": {"name": "obsidian-docs", "version": "1.0.0"},
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
    args = ap.parse_args()

    global VAULT
    caminho = args.vault or os.environ.get("OBSIDIAN_VAULT")
    if caminho:
        caminho = os.path.abspath(os.path.expanduser(caminho))
    if caminho and os.path.isdir(caminho):
        VAULT = caminho
    else:
        origem = caminho or "OBSIDIAN_VAULT nao definido"
        print(f"servidor_vault: vault indisponivel ({origem}); "
              "ferramentas vao instruir a configuracao", file=sys.stderr)

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
