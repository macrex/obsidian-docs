#!/usr/bin/env python3
"""Autoteste do servidor: vault temporario, depois um vault git com remoto local.

  python mcp/teste_servidor_vault.py

Cobre o que a convencao exige e o modelo nao pode esquecer: hub/Home novos,
frontmatter, link do hub no corpo, entrada no hub sem duplicar, ticket em
pasta propria, mapa na raiz, ordem alfabetica no Home, lifecycle (status,
sucessora), resumo no hub, wikilink quebrado avisado e commit -> push.
"""
import importlib.util
import os
import shutil
import subprocess
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("sv", os.path.join(AQUI, "servidor_vault.py"))
sv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sv)


def arq(*partes):
    return open(os.path.join(sv.VAULT, *partes), encoding="utf-8").read()


def erro_de_uso(fn, **kw):
    try:
        fn(**kw)
    except sv.ErroUso as e:
        return str(e)
    raise AssertionError("esperava ErroUso")


with tempfile.TemporaryDirectory() as tmp:
    sv.VAULT, sv.SEM_GIT = tmp, True

    # projeto novo sem descricao -> erro que manda conferir visao_geral
    assert "descricao_projeto" in erro_de_uso(sv.salvar_nota, projeto="demo", tipo="spec",
                                              titulo="Login", corpo="x", resumo="r")
    r = sv.salvar_nota(projeto="demo", tipo="spec", titulo="Login", corpo="Corpo da spec.",
                       resumo="spec de login", descricao_projeto="Projeto demo.",
                       repo="/tmp/demo", data="2026-01-02")
    assert "Salva: demo/Specs/2026-01-02 Login.md" in r, r
    assert "- [[demo]] — Projeto demo" in arq("Home.md")
    hub = arq("demo", "demo.md")
    assert "Projeto demo. Hub global: [[Home]]." in hub and "Repo: /tmp/demo" in hub
    assert "## Specs" in hub and "- [[2026-01-02 Login]] — spec de login" in hub
    nota = arq("demo", "Specs", "2026-01-02 Login.md")
    assert nota.startswith("---\nprojeto: demo\ntipo: spec\nstatus: ativo\n"
                           "data: 2026-01-02\ntags: []\n---\n"), nota
    assert "# Login\n\nProjeto: [[demo]]\n\nCorpo da spec." in nota, nota

    # duplicata nao sobrescreve
    assert "ja existe" in erro_de_uso(sv.salvar_nota, projeto="demo", tipo="spec",
                                      titulo="Login", corpo="y", resumo="r", data="2026-01-02")

    # ticket -> pasta do artefato; secao do hub nao duplica; entrada vai depois
    r = sv.salvar_nota(projeto="demo", tipo="plano", titulo="Ticket 01", corpo="t",
                       resumo="ticket 1", artefato="2026-01-02 Login.md", data="2026-01-03")
    assert "demo/Specs/Tickets - 2026-01-02 Login/2026-01-03 Ticket 01.md" in r, r
    hub = arq("demo", "demo.md")
    assert hub.count("## Specs") == 1 and hub.index("Login]]") < hub.index("Ticket 01]]")
    assert "ticket" in erro_de_uso(sv.salvar_nota, projeto="demo", tipo="bug", titulo="B",
                                   corpo="b", resumo="r", artefato="2026-01-02 Login")

    # mapa: nome fixo na raiz, secao Mapa, regrava sem reclamar
    for _ in range(2):
        r = sv.salvar_nota(projeto="demo", tipo="mapa", titulo="x", corpo="Dominios.")
        assert "Salva: demo/Mapa do Codigo demo.md" in r, r
    hub = arq("demo", "demo.md")
    assert hub.count("[[Mapa do Codigo demo]]") == 1 and "## Mapa" in hub

    # segundo projeto -> Home em ordem alfabetica, tipo com acento normalizado
    sv.salvar_nota(projeto="alpha", tipo="evolução", titulo="Leva 1", corpo="b", resumo="leva",
                   descricao_projeto="Alpha", tags=["leva", "v1"])
    home = arq("Home.md")
    assert home.index("[[alpha]]") < home.index("[[demo]]"), home
    assert "tags: [leva, v1]" in arq("alpha", "Evolucoes", sv.hoje() + " Leva 1.md")

    # lifecycle: sucessora -> obsoleto + link no topo
    sv.atualizar_nota(nota="2026-01-02 Login", sucessora="2026-01-03 Ticket 01")
    nota = arq("demo", "Specs", "2026-01-02 Login.md")
    assert "status: obsoleto" in nota and "Substituída por [[2026-01-03 Ticket 01]]" in nota
    assert "sucessora nao existe" in erro_de_uso(sv.atualizar_nota, nota="2026-01-02 Login",
                                                 sucessora="Nada")

    # corpo + status + resumo no hub
    r = sv.atualizar_nota(nota="demo/Specs/Tickets - 2026-01-02 Login/2026-01-03 Ticket 01.md",
                          corpo="Novo corpo.", status="resolvido", resumo="feito")
    nota = arq("demo", "Specs", "Tickets - 2026-01-02 Login", "2026-01-03 Ticket 01.md")
    assert "# Ticket 01\n\nProjeto: [[demo]]\n\nNovo corpo." in nota and "status: resolvido" in nota
    assert "- [[2026-01-03 Ticket 01]] — feito" in arq("demo", "demo.md")
    assert "hub" in erro_de_uso(sv.atualizar_nota, nota="demo", status="ativo")

    # leitura enxerga a escrita; wikilink quebrado e avisado
    assert "2026-01-03 Ticket 01" in sv.buscar("novo corpo")
    r = sv.salvar_nota(projeto="demo", tipo="analise", titulo="Estudo", corpo="Ver [[Nao Existe]].",
                       resumo="estudo")
    assert "[[Nao Existe]]" in r and "sem git" in r, r

# vault git com remoto: cada gravacao commita e empurra
if shutil.which("git"):
    def g(*a, cwd):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)

    with tempfile.TemporaryDirectory() as t2:
        bare, vault = os.path.join(t2, "remoto.git"), os.path.join(t2, "vault")
        g("init", "--bare", bare, cwd=t2)
        g("clone", bare, vault, cwd=t2)
        g("config", "user.email", "t@t", cwd=vault)
        g("config", "user.name", "t", cwd=vault)
        open(os.path.join(vault, ".gitignore"), "w").write(".obsidian/workspace.json\n")
        g("add", "-A", cwd=vault)
        g("commit", "-m", "init", cwd=vault)
        g("push", "-u", "origin", "HEAD", cwd=vault)
        sv.VAULT, sv.SEM_GIT = vault, False
        r = sv.salvar_nota(projeto="demo", tipo="spec", titulo="X", corpo="x", resumo="x",
                           descricao_projeto="Demo")
        assert "commit + push ok" in r, r
        assert "demo: X" in g("log", "--oneline", "-1", cwd=bare).stdout
        sv.SEM_GIT = True
        assert "sem git" in sv.atualizar_nota(nota=sv.hoje() + " X", status="resolvido")
else:
    print("git ausente: teste de commit/push pulado")

print("ok")
