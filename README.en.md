# obsidian-docs

> [Português](README.md) · **English**

[Claude Code](https://claude.com/claude-code) skills that keep your project documentation in an
Obsidian vault instead of inside the repositories. **The repo holds code, the vault holds
memory**: specs, plans, ADRs, bugs and release notes become a navigable graph, with one hub per
project and wikilinks between notes.

The skill files themselves are written in Portuguese (pt-BR) — Claude reads them fine either
way, and your own prompts and `CLAUDE.md` can be in English.

| Piece | What it does |
|---|---|
| MCP `vault-docs` | The server. Reads the vault by search and writes notes already in the conventions (folder, name, frontmatter, hub, git). |
| `/obsidian-docs` | The everyday skill: decides what to document, writes the content and calls the server. |
| `/obsidian-docs-update` | Migrates **one** project's docs to the vault, by copy (the repo is left untouched). |
| `/obsidian-docs-update-all` | Same migration, across the whole workspace. Uses the `vault-migrador` agent. |

Structure kept in the vault: global `Home.md` → `<project>/<project>.md` (hub) → `Specs/`,
`Arquitetura/`, `Bugs/`, `Evolucoes/`, `Analises/`. Every note carries frontmatter
(`projeto`, `tipo`, `status`, `data`), links its hub and is indexed there — the server
guarantees that in code, not in the model's memory.

## Install

**1. Clone and link the skills** (Windows: `New-Item -ItemType SymbolicLink -Path ... -Target ...`,
or copy the folders):

```bash
git clone https://github.com/macrex/obsidian-docs.git ~/repos/obsidian-docs

for s in obsidian-docs obsidian-docs-update obsidian-docs-update-all; do
  ln -s ~/repos/obsidian-docs/$s ~/.claude/skills/$s
done
ln -s ~/repos/obsidian-docs/agents/vault-migrador.md ~/.claude/agents/vault-migrador.md
```

**2. Register the server**, pointing at the *projects* folder inside your vault:

```bash
python ~/repos/obsidian-docs/mcp/servidor_vault.py --instalar --vault ~/obsidian/projetos
```

That's it. Python 3.9+, no dependencies. The command registers the server in Claude Code's user
scope — it works in every project of yours — and can be repeated safely. If you already have an
`OBSIDIAN_VAULT` variable, `--vault` is optional. A vault that is a git repository gets commit +
`pull --rebase` + push on every write; add `--sem-git` to turn that off.

**3. Restart Claude Code** and check: `claude mcp list` shows `vault-docs … ✔ Connected`.

## Server tools

| Tool | What it does |
|---|---|
| `visao_geral` | Overview: projects, note counts by type, recent notes. |
| `buscar` | Accent/case-insensitive full-text search, `projeto`/`tipo`/`status` filters, with snippet. |
| `listar_notas` | Path + frontmatter, newest first. |
| `ler_nota` | Full note content, by relative path or wikilink name. |
| `conexoes` | Outgoing wikilinks and backlinks — graph navigation. |
| `salvar_nota` | New note: folder by type, `YYYY-MM-DD title.md`, frontmatter, hub link and hub entry, hub/`Home.md` when the project is new, commit+push. Tickets go to `Specs/Tickets - <artefato>/`. |
| `atualizar_nota` | Existing note: body, status, tags, hub summary, or successor (marks obsolete and links it). |
| `mapa_codigo` | Code map of the project read from `graphify-out/`: graph freshness, communities, god nodes. |
| `consultar_codigo` | Architecture question to the graph (`graphify query/explain/path`), local CLI. |
| `gerar_mapa` | Rewrites the `Mapa do Codigo <project>` note from the graph, keeping your curated reading. |

Self-test, in a temporary vault: `python ~/repos/obsidian-docs/mcp/teste_servidor_vault.py`.
End-to-end sandbox test (git vault with a remote and a second concurrent clone, a real repo
indexed by graphify, the server speaking MCP over stdin, linter at the end):
`python ~/repos/obsidian-docs/mcp/teste_sandbox.py`. Neither touches your vault.

## graphify (optional): the code graph as a second source

[graphify](https://github.com/Graphify-Labs/graphify) (`pip install graphifyy`, free, runs
locally, no key needed for code) turns a repository into a graph — nodes are files, functions and
classes; edges are "calls" and "contains" — written to `graphify-out/graph.json`. The server
reads that file and nothing else: no API calls, no graphify process required, and only
`consultar_codigo` uses the CLI.

**Wiring a project, in three steps:**

1. Build the graph inside the repository: `graphify update .` (or the `graphify-ai` facilitator
   skill, which also installs the git hook that rebuilds the graph on every commit). Add
   `graphify-out/` to the project's `.gitignore` — besides the graph, graphify writes `cache/`
   and `manifest.json` there, and on a large project that passes 50 MB.
2. Point the project's hub in the vault at the repository: the `Repo: <path>` line in
   `<project>/<project>.md`. No hand editing needed — the first call with `repo=` writes the line,
   and a call with a different `repo=` updates it when the repository moves. A hand-written hub
   with decorations (`Repo: **\`D:\x\`** on master`) works too: only the path counts.
3. Done. With no graph, the code tools answer "sem grafo em <folder>" and the rest of the
   server works unchanged — nothing in the vault depends on graphify.

| Tool | What it does with the graph |
|---|---|
| `mapa_codigo <project>` | Freshness (compares `built_at_commit` with the repo's `HEAD`: "atualizado" or "atrasado N commits"), ten god nodes by degree, the 20 largest communities with their `.graphify_labels.json` label, and the highlights of `GRAPH_REPORT.md`. Read it before touching a project. |
| `consultar_codigo <project>` | One question at a time to the CLI: a free `pergunta` (`graphify query`), `explicar` a node, or `caminho=[A, B]` (shortest path). |
| `gerar_mapa <project>` | Rewrites the `Mapa do Codigo <project>` note with god nodes, communities and highlights, preserving the `## Leitura curada` section — pass `leitura` to update it. Call it after every graphify run. |
| `salvar_nota … arquivos=[…]` | Matches each path to graph nodes and appends `## Componentes tocados` to the note (the six communities with most touched nodes, five labels each), linking the Mapa. Files without a node are listed; a missing graph only yields a warning. |

**Two sources, one question each.** The vault knows what was decided and written; the graph
knows what the code is now. Why it is this way and what was already ruled out → vault
(`ler_nota`, `buscar`). Who calls X, path from A to B, which file is the bottleneck → graph
(`consultar_codigo`, `mapa_codigo`). A project you don't know → hub + latest evolution +
`mapa_codigo`.

**Never inside the vault.** The vault is a git repository and the server commits and pushes on
every note; a `graph.json` there would reach the remote by itself, on every rebuild.

## CLAUDE.md

The skills only kick in on their own if the routing rules are in your `CLAUDE.md`. Minimum:

```markdown
# obsidian-docs
- Every documentation .md artifact (spec, plan, design, bug, release note, ADR, architecture,
  analysis, research, report) → the `obsidian-docs` skill, which writes to the vault through
  the `vault-docs` MCP (`salvar_nota`). NEVER in the project repo.
- Finding and reading docs: `buscar`, `ler_nota`, `listar_notas`, `conexoes`, `visao_geral`.
  Never Read/Grep/Write/Edit the vault files directly, never run git in it.
- Updating an existing doc → `atualizar_nota` (in place), never recreate it in the repo.
- Migrating to the vault is a COPY, never a move: deleting or moving files from the repo is
  forbidden.
```

Optional, ordered by how much they change the outcome:

```markdown
- **The vault is the projects' memory.** Before touching code, read the hub
  (`ler_nota <repo-folder-name>`) and the latest note in `Evolucoes/`
  (`listar_notas projeto=<project> tipo=evolucao limite=1`) — retracing a path already proven
  wrong costs the session.
- **When closing a batch/version: record the evolution** (`salvar_nota tipo=evolucao`). One
  note per batch, with verification and open items. (This is what feeds the rule above.)
- Bulk-migrating docs to the vault: `obsidian-docs-update` (one project) or
  `obsidian-docs-update-all` (whole workspace).
- Brainstorming specs/plans (superpowers) also go to the vault.
- After running graphify → `gerar_mapa <project>` with your `leitura`. `graphify-out/` stays in
  the repo and in `.gitignore`, never in the vault. Before touching code, `mapa_codigo <project>`
  alongside the hub; structure questions go to the graph (`consultar_codigo`), decision
  questions to the vault.
- A project mentioned that isn't in the cwd → resolve it before acting: `ler_nota <project>`;
  unsure of the name → `buscar <name>` or `visao_geral`.
```

## Notes

- Works with Obsidian closed: it is all filesystem, no plugin. The server is the vault's only
  door — so no note is ever born orphan, without frontmatter or outside its hub.
- Optional whole-vault linter (`scripts/validar_vault.py --resumo`): checks frontmatter, broken
  links and notes missing from the hub in older vaults that predate the server.
- Bulk migration always shows `file → destination → type` and **waits for confirmation** before
  writing. Nothing is deleted from the repo — a `.md` can be operational code (build
  instructions, a note inside a vendored lib) and the classifier can't tell.
- `README`, `CLAUDE.md`, `AGENTS.md`, `SKILL.md`, `LICENSE` and configs are never migrated.

MIT — see [LICENSE](LICENSE).
