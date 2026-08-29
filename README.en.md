# obsidian-docs

> [Português](README.md) · **English**

[Claude Code](https://claude.com/claude-code) skills that keep your project documentation in an
Obsidian vault instead of inside the repositories. **The repo holds code, the vault holds
memory**: specs, plans, ADRs, bugs and release notes become a navigable graph, with one hub per
project and wikilinks between notes.

The skill files themselves are written in Portuguese (pt-BR) — Claude reads them fine either
way, and your own prompts and `CLAUDE.md` can be in English.

| Skill | What it does |
|---|---|
| `/obsidian-docs` | Creates, updates and finds docs in the vault. The everyday one. |
| `/obsidian-docs-update` | Migrates **one** project's docs to the vault, by copy (the repo is left untouched). |
| `/obsidian-docs-update-all` | Same migration, across the whole workspace. Uses the `vault-migrador` agent. |

Structure kept in the vault: global `Home.md` → `<project>/<project>.md` (hub) → `Specs/`,
`Arquitetura/`, `Bugs/`, `Evolucoes/`, `Analises/`. Every note carries frontmatter
(`projeto`, `tipo`, `status`, `data`) and is indexed in its hub.

## Install

```bash
git clone https://github.com/macrex/obsidian-docs.git ~/repos/obsidian-docs

for s in obsidian-docs obsidian-docs-update obsidian-docs-update-all; do
  ln -s ~/repos/obsidian-docs/$s ~/.claude/skills/$s
done
ln -s ~/repos/obsidian-docs/agents/vault-migrador.md ~/.claude/agents/vault-migrador.md
```

Windows: `New-Item -ItemType SymbolicLink -Path ... -Target ...` (needs admin or Developer
Mode). Copying the folders works too — it just won't update with `git pull`.

**Tell it where the vault is** — without this the skills stop and ask (they never guess a
path). Point at the *projects* folder inside the vault:

```bash
export OBSIDIAN_VAULT="$HOME/obsidian/projetos"     # ~/.zshrc, ~/.bashrc
```

Optional linter — checks frontmatter, broken links and orphan notes:

```bash
mkdir -p "$OBSIDIAN_VAULT/.scripts"
cp ~/repos/obsidian-docs/scripts/validar_vault.py "$OBSIDIAN_VAULT/.scripts/"
python "$OBSIDIAN_VAULT/.scripts/validar_vault.py" --resumo
```

## MCP server (optional)

`mcp/servidor_vault.py` exposes the vault as MCP tools — the LLM queries the docs through
search instead of crawling files one by one. Zero dependencies (Python 3.9+, stdlib only).
Register once, works in every project:

```bash
claude mcp add --scope user vault-docs -- python3 ~/repos/obsidian-docs/mcp/servidor_vault.py
```

Windows: use `python` instead of `python3`. The vault path comes from `OBSIDIAN_VAULT`; without
the variable, append `--vault <path>` at the end of the command. Tools (all read-only):

| Tool | What it does |
|---|---|
| `visao_geral` | Overview: projects, note counts by type, recent notes. |
| `buscar` | Accent/case-insensitive full-text search, `projeto`/`tipo`/`status` filters, with snippet. |
| `listar_notas` | Path + frontmatter, newest first. |
| `ler_nota` | Full note content, by relative path or wikilink name. |
| `conexoes` | Outgoing wikilinks and backlinks — graph navigation. |

The skills keep working without it — the MCP just makes finding and reading docs cheaper and
more direct. Opening this repo in Claude Code picks the server up via `.mcp.json`
(project scope).

## CLAUDE.md

The skills only kick in on their own if the routing rules are in your `CLAUDE.md`. Minimum:

```markdown
# obsidian-docs
- Documentation vault: `OBSIDIAN_VAULT` env var (or `<path>/obsidian/projetos`).
- Every documentation .md artifact (spec, plan, design, bug, release note, ADR, architecture,
  analysis, research, report) → invoke the `obsidian-docs` skill and save it in the vault,
  NEVER in the project repo. Reading old docs: same skill, on demand.
- Updating an existing doc: edit the note directly in the vault (in place), never recreate it
  in the repo.
- Migrating to the vault is a COPY, never a move: deleting or moving files from the repo is
  forbidden.
```

Optional, ordered by how much they change the outcome:

```markdown
- **The vault is the projects' memory.** Before touching code, check whether
  `<vault>/<repo-folder-name>/` exists and read at least the hub and the latest note in
  `Evolucoes/` — retracing a path already proven wrong costs the session.
- **When closing a batch/version: record it in `Evolucoes/`** and index it in the hub. One note
  per batch, with verification and open items. (This is what feeds the rule above.)
- Bulk-migrating docs to the vault: `obsidian-docs-update` (one project) or
  `obsidian-docs-update-all` (whole workspace).
- Versioned vault: commit + `pull --rebase` + push automatically when editing a note, without
  asking — an exception limited to that repo.
- Brainstorming specs/plans (superpowers) also go to the vault.
- After running graphify → update `Mapa do Codigo <project>.md` in the vault. `graphify-out/`
  stays local and in `.gitignore`, never in the vault.
- A project mentioned that isn't in the cwd → resolve it via the `<vault>/Home.md` catalog
  before acting.
```

## Notes

- Works with Obsidian closed: the skills write to the filesystem, no plugin and no MCP
  required — the server above is optional, for querying only.
- Bulk migration always shows `file → destination → type` and **waits for confirmation** before
  writing. Nothing is deleted from the repo — a `.md` can be operational code (build
  instructions, a note inside a vendored lib) and the classifier can't tell.
- `README`, `CLAUDE.md`, `AGENTS.md`, `SKILL.md`, `LICENSE` and configs are never migrated.

MIT — see [LICENSE](LICENSE).
