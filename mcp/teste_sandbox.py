#!/usr/bin/env python3
"""Teste de ponta a ponta em sandbox descartavel — nada toca o vault real.

  python mcp/teste_sandbox.py

Monta num diretorio temporario: um remoto git bare, o vault clonado dele, um
segundo clone (outra maquina escrevendo ao mesmo tempo), e um repositorio de
codigo real indexado pelo graphify instalado (sem ele, grafo sintetico). O
servidor roda como processo separado e conversa pelo protocolo MCP (JSON-RPC
por stdin), exatamente como o Claude Code faz. O linter do vault confere o
resultado no fim.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
SERVIDOR = os.path.join(AQUI, "servidor_vault.py")
LINTER = os.path.join(AQUI, "..", "scripts", "validar_vault.py")


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def repo_git(caminho):
    os.makedirs(caminho, exist_ok=True)
    git(caminho, "init", "-q")
    git(caminho, "config", "user.email", "sandbox@teste")
    git(caminho, "config", "user.name", "sandbox")


class Sessao:
    """Um processo do servidor por sessao, como o Claude Code faz."""

    def __init__(self, vault, *extra):
        # stderr nunca vai para um pipe sem leitor: cheio, ele travaria os dois lados
        self.p = subprocess.Popen([sys.executable, SERVIDOR, "--vault", vault, *extra],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        self.n = 0
        r = self.rpc("initialize", {"protocolVersion": "2025-06-18"})
        assert r["serverInfo"]["name"] == "obsidian-docs", r

    def bruto(self, linha):
        self.p.stdin.write(linha + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def rpc(self, metodo, params=None):
        self.n += 1
        msg = self.bruto(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": metodo,
                                     "params": params or {}}, ensure_ascii=False))
        assert msg.get("id") == self.n, msg
        return msg["error"] if "error" in msg else msg["result"]

    def tool(self, nome, **args):
        r = self.rpc("tools/call", {"name": nome, "arguments": args})
        return r["content"][0]["text"], bool(r.get("isError"))

    def ok(self, nome, **args):
        texto, erro = self.tool(nome, **args)
        assert not erro, f"{nome}: {texto}"
        return texto

    def erro(self, nome, **args):
        texto, erro = self.tool(nome, **args)
        assert erro, f"{nome} devia falhar: {texto}"
        return texto

    def fecha(self):
        self.p.stdin.close()
        self.p.wait(timeout=15)
        self.p.stdout.close()


with tempfile.TemporaryDirectory() as t:
    bare, vault, outro = (os.path.join(t, n) for n in ("remoto.git", "vault", "outro-clone"))
    repo = os.path.join(t, "projeto-x")

    # vault versionado com remoto, e um segundo clone que tambem escreve
    git(t, "init", "-q", "--bare", bare)
    for clone in (vault, outro):
        git(t, "clone", "-q", bare, clone)
        git(clone, "config", "user.email", "sandbox@teste")
        git(clone, "config", "user.name", "sandbox")
    os.makedirs(os.path.join(vault, ".scripts"))
    shutil.copy(LINTER, os.path.join(vault, ".scripts", "validar_vault.py"))
    with open(os.path.join(vault, ".gitignore"), "w") as f:
        f.write(".obsidian/workspace.json\n")
    git(vault, "add", "-A")
    git(vault, "commit", "-q", "-m", "vault inicial")
    git(vault, "push", "-q", "-u", "origin", "HEAD")
    git(outro, "pull", "-q")

    # repositorio de codigo real: os proprios fontes deste projeto
    repo_git(repo)
    for f in (SERVIDOR, os.path.join(AQUI, "teste_servidor_vault.py"), LINTER):
        shutil.copy(f, repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "codigo")
    exe = shutil.which("graphify")
    if exe:
        try:  # graphify pendurado ou interativo nao derruba o teste: cai no grafo sintetico
            subprocess.run([exe, "update", "."], cwd=repo, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            pass
    grafo_real = os.path.exists(os.path.join(repo, "graphify-out", "graph.json"))
    if not grafo_real:  # sem o CLI, um grafo minimo mantem o resto do teste valido
        os.makedirs(os.path.join(repo, "graphify-out"), exist_ok=True)
        with open(os.path.join(repo, "graphify-out", "graph.json"), "w") as f:
            json.dump({"nodes": [{"id": "s", "label": "servidor_vault.py",
                                  "source_file": "servidor_vault.py", "community": "0"}],
                       "links": [], "built_at_commit": git(repo, "rev-parse", "HEAD")[1]}, f)

    s = Sessao(vault)
    nomes = [x["name"] for x in s.rpc("tools/list")["tools"]]
    assert len(nomes) == 10 and "salvar_nota" in nomes, nomes
    assert "Vault vazio" in s.ok("visao_geral")

    # projeto novo: primeiro sem descricao (erro de uso), depois certo
    assert "descricao_projeto" in s.erro("salvar_nota", projeto="projeto-x", tipo="spec",
                                         titulo="Login", corpo="x", resumo="r")
    r = s.ok("salvar_nota", projeto="projeto-x", tipo="spec", titulo="Login",
             corpo="Spec do login com [[Home]].", resumo="spec de login",
             descricao_projeto="Projeto X de teste", repo=repo, tags=["login"])
    assert "commit + push ok" in r, r
    assert "projeto-x: Login" in git(bare, "log", "--oneline", "-1")[1]
    home = s.ok("ler_nota", nota="Home")
    assert "- [[projeto-x]] — Projeto X de teste" in home, home
    assert "ja existe" in s.erro("salvar_nota", projeto="projeto-x", tipo="spec",
                                 titulo="Login", corpo="y", resumo="r")
    assert "tipo invalido" in s.erro("salvar_nota", projeto="projeto-x", tipo="poema",
                                     titulo="T", corpo="c", resumo="r")

    # grafo (real, se o graphify estiver instalado)
    m = s.ok("mapa_codigo", projeto="projeto-x")
    assert "atualizado" in m and "God nodes" in m and "Comunidades (" in m, m
    if grafo_real:
        assert "servidor_vault.py" in m, m
        q, erro = s.tool("consultar_codigo", projeto="projeto-x", explicar="salvar_nota()")
        assert q.strip() and (not erro or "graphify falhou" in q), q
    assert "exatamente um" in s.erro("consultar_codigo", projeto="projeto-x")

    # componentes tocados com arquivo real + arquivo inexistente
    r = s.ok("salvar_nota", projeto="projeto-x", tipo="evolucao", titulo="Leva 1",
             corpo="O que mudou.", resumo="primeira leva",
             arquivos=["servidor_vault.py", "nao_existe.py"])
    assert "Componentes:" in r and "1 arquivo(s) sem nó" in r, r
    nota = s.ok("ler_nota", nota="Leva 1")
    assert "## Componentes tocados" in nota and "nao_existe.py" in nota, nota

    # mapa curado: leitura preservada na segunda rodada
    assert "Mapa do Codigo projeto-x.md" in s.ok("gerar_mapa", projeto="projeto-x",
                                                 leitura="Leitura curada de teste.")
    s.ok("gerar_mapa", projeto="projeto-x")
    mapa = s.ok("ler_nota", nota="Mapa do Codigo projeto-x")
    assert "Leitura curada de teste." in mapa and "## God nodes" in mapa, mapa

    # lifecycle e indice
    s.ok("atualizar_nota", nota="Login", sucessora="Leva 1")
    assert "status: obsoleto" in s.ok("ler_nota", nota="Login")
    s.ok("atualizar_nota", nota="Leva 1", status="resolvido", resumo="leva fechada")
    assert "- [[" in s.ok("ler_nota", nota="projeto-x") and "leva fechada" in s.ok("ler_nota", nota="projeto-x")
    assert "hub" in s.erro("atualizar_nota", nota="projeto-x", status="ativo")
    assert "Leva 1" in s.ok("buscar", consulta="mudou")
    assert "2 de 2" in s.ok("listar_notas", projeto="projeto-x", tipo="evolucao") or \
           "1 de 1" in s.ok("listar_notas", projeto="projeto-x", tipo="evolucao")
    assert "Backlinks" in s.ok("conexoes", nota="projeto-x")

    # outra maquina empurrou antes: o servidor faz rebase e ainda assim empurra
    git(outro, "pull", "-q", "--rebase")
    with open(os.path.join(outro, "nota-de-fora.md"), "w") as f:
        f.write("---\nprojeto: vault\ntipo: analise\nstatus: ativo\ndata: 2026-01-01\n---\n# Fora\n")
    git(outro, "add", "-A")
    git(outro, "commit", "-q", "-m", "de outra maquina")
    git(outro, "push", "-q")
    r = s.ok("salvar_nota", projeto="projeto-x", tipo="bug", titulo="Falha", corpo="Bug.",
             resumo="um bug")
    assert "commit + push ok" in r, r
    assert git(vault, "status", "--porcelain")[1] == "", "working tree do vault sujo"
    assert git(vault, "rev-list", "--count", "@{u}..HEAD")[1] == "0", "commit sem push"
    assert os.path.exists(os.path.join(vault, "nota-de-fora.md")), "rebase nao trouxe o commit de fora"

    # protocolo: metodo desconhecido e JSON invalido nao derrubam o servidor
    assert "metodo desconhecido" in s.rpc("nao/existe")["message"]
    assert s.bruto("isto nao e json")["error"]["code"] == -32700
    assert "Vault:" in s.ok("visao_geral")
    s.fecha()

    # --sem-git: grava, nao commita
    s2 = Sessao(vault, "--sem-git")
    assert "sem git" in s2.ok("salvar_nota", projeto="projeto-x", tipo="analise",
                              titulo="Estudo", corpo="Estudo.", resumo="um estudo")
    s2.fecha()
    assert git(vault, "status", "--porcelain")[1] != "", "--sem-git devia deixar pendente"

    # linter do vault sobre tudo que o servidor escreveu
    lint = subprocess.run([sys.executable, ".scripts/validar_vault.py", "--resumo"], cwd=vault,
                          capture_output=True, text=True, encoding="utf-8")
    assert "Erros: 0" in lint.stdout, lint.stdout + lint.stderr

print("ok" + ("" if grafo_real else " (graphify ausente: grafo sintetico)"))
