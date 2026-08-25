#!/usr/bin/env python3
"""Linter do vault Obsidian: acha o que quebra a navegacao e o padrao.

Uso:
  python .scripts/validar_vault.py            # relatorio + exit 1 se houver erro
  python .scripts/validar_vault.py --resumo   # so o placar
  python .scripts/validar_vault.py --tipo orfas   # so uma checagem

Checagens:
  E1 nota sem frontmatter
  E2 campo obrigatorio ausente (projeto, tipo, status, data)
  E3 valor fora do vocabulario (tipo/status)
  E4 wikilink apontando para nota inexistente
  E5 nota de projeto nao listada no hub do projeto
  A1 (aviso) nota orfa: ninguem linka para ela
  A2 (aviso) nota sem nenhum wikilink de saida
  A3 (aviso) projeto sem hub
"""
import argparse
import os
import re
import sys
from collections import defaultdict

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIPOS = {"hub", "spec", "plano", "bug", "evolucao", "arquitetura", "adr", "analise", "mapa"}
STATUS = {"ativo", "rascunho", "resolvido", "obsoleto"}
OBRIGATORIOS = ("projeto", "tipo", "status", "data")
IGNORAR = {".obsidian", ".scripts", ".git"}
# [[alvo]] e [[alvo|texto]]; ignora blocos de codigo (```...```)
WIKILINK_RE = re.compile(r"\[\[([^\]\[|#]+)")
CODEBLOCK_RE = re.compile(r"```.*?```", re.S)
INLINECODE_RE = re.compile(r"`[^`\n]+`")   # `[[exemplo]]` em prosa nao e link real


def notas():
    """Arquivos .md do vault (as notas em si)."""
    for caminho, ext in arquivos_do_vault():
        if ext == ".md":
            yield caminho


def arquivos_do_vault():
    """(caminho, extensao) de tudo que o Obsidian trata como link valido."""
    for raiz, dirs, arqs in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for a in arqs:
            ext = os.path.splitext(a)[1].lower()
            if ext in (".md", ".base", ".canvas"):
                yield os.path.join(raiz, a), ext


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


def projeto_de(caminho):
    rel = os.path.relpath(caminho, VAULT)
    partes = rel.split(os.sep)
    return partes[0] if len(partes) > 1 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resumo", action="store_true")
    ap.add_argument("--tipo", default=None, help="orfas | frontmatter | links | hub")
    args = ap.parse_args()

    erros, avisos = [], []
    por_nome, links_para, com_link_saida = {}, defaultdict(list), set()
    projetos = defaultdict(list)

    for caminho in notas():
        rel = os.path.relpath(caminho, VAULT)
        nome = os.path.splitext(os.path.basename(caminho))[0]
        por_nome[nome] = rel
        texto = open(caminho, encoding="utf-8").read()
        proj = projeto_de(caminho)
        if proj:
            projetos[proj].append(nome)

        fm = frontmatter(texto)
        if fm is None:
            erros.append(("E1", rel, "sem frontmatter"))
        else:
            for campo in OBRIGATORIOS:
                if campo not in fm:
                    erros.append(("E2", rel, f"campo '{campo}' ausente"))
            tipo, status = fm.get("tipo"), fm.get("status")
            if tipo and tipo not in TIPOS and "|" not in tipo:
                erros.append(("E3", rel, f"tipo invalido: '{tipo}'"))
            if status and status not in STATUS and "|" not in status:
                erros.append(("E3", rel, f"status invalido: '{status}'"))

        corpo = INLINECODE_RE.sub("", CODEBLOCK_RE.sub("", texto))
        alvos = {a.strip() for a in WIKILINK_RE.findall(corpo) if a.strip()}
        if alvos:
            com_link_saida.add(nome)
        for alvo in alvos:
            links_para[alvo].append(rel)

    # alvos validos incluem .base/.canvas (linkaveis no Obsidian, mas nao sao notas)
    alvos_validos = set(por_nome)
    for caminho, ext in arquivos_do_vault():
        if ext != ".md":
            base = os.path.basename(caminho)
            alvos_validos.add(base)                          # [[Bugs abertos.base]]
            alvos_validos.add(os.path.splitext(base)[0])     # [[Bugs abertos]]

    # E4 links quebrados
    for alvo, origens in sorted(links_para.items()):
        if alvo not in alvos_validos:
            erros.append(("E4", origens[0], f"wikilink quebrado: [[{alvo}]]"))

    # E5/A3 hubs
    for proj, nomes in sorted(projetos.items()):
        if proj not in por_nome:
            avisos.append(("A3", proj + "/", "projeto sem hub"))
            continue
        hub_txt = open(os.path.join(VAULT, por_nome[proj]), encoding="utf-8").read()
        citados = set(WIKILINK_RE.findall(hub_txt))
        for nome in nomes:
            if nome != proj and nome not in citados:
                erros.append(("E5", f"{proj}/{nome}.md", "nao listada no hub"))

    # A1/A2 conectividade
    for nome, rel in sorted(por_nome.items()):
        if nome not in links_para and nome != "Home":
            avisos.append(("A1", rel, "orfa: ninguem linka para ela"))
        if nome not in com_link_saida:
            avisos.append(("A2", rel, "sem wikilink de saida"))

    filtro = {"frontmatter": ("E1", "E2", "E3"), "links": ("E4", "A2"),
              "orfas": ("A1",), "hub": ("E5", "A3")}.get(args.tipo)
    if filtro:
        erros = [e for e in erros if e[0] in filtro]
        avisos = [a for a in avisos if a[0] in filtro]

    if not args.resumo:
        for cod, onde, msg in erros:
            print(f"ERRO  {cod} {onde}: {msg}")
        for cod, onde, msg in avisos[:40]:
            print(f"aviso {cod} {onde}: {msg}")
        if len(avisos) > 40:
            print(f"aviso ... e mais {len(avisos) - 40} avisos")

    contagem = defaultdict(int)
    for cod, _, _ in erros + avisos:
        contagem[cod] += 1
    print(f"\nNotas: {len(por_nome)} | Projetos: {len(projetos)}")
    print(f"Erros: {len(erros)} | Avisos: {len(avisos)}")
    for cod in sorted(contagem):
        print(f"  {cod}: {contagem[cod]}")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
