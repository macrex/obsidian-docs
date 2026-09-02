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

Self-test, in a temporary vault: `python ~/repos/obsidian-docs/mcp/teste_servidor_vault.py`.

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
- After running graphify → `salvar_nota tipo=mapa` (`Mapa do Codigo <project>`).
  `graphify-out/` stays local and in `.gitignore`, never in the vault.
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
