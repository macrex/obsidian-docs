# obsidian-docs — moved to macrex/skills

This repository is **discontinued**. The three skills and the `vault-docs` MCP server now live in
**[macrex/skills](https://github.com/macrex/skills)**, alongside the other skills, and that is
where you install them from:

```bash
npx skills add https://github.com/macrex/skills -g --skill obsidian-docs --skill obsidian-docs-update --skill obsidian-docs-update-all
```

Why it moved: the skills CLI copies **only the skill folder**, so an MCP server living outside it
is never installed along. In the new repository `servidor_vault.py` travels inside the
`obsidian-docs` skill, under `scripts/`, with the vault tests and linter next to it and the
`vault-migrador` agent in `assets/` — one install covers everything. Server registration, the
tool table, the graphify part and the `CLAUDE.md` routing are documented in that README.

The code that used to live here remains in this repository's history.

MIT — see [LICENSE](LICENSE).
