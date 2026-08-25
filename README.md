# obsidian-docs

> **Português** · [English](README.en.md)

Skills de [Claude Code](https://claude.com/claude-code) que guardam a documentação dos seus
projetos num vault Obsidian em vez de dentro dos repositórios. **O repo guarda código, o vault
guarda memória**: spec, plano, ADR, bug e nota de evolução viram um grafo navegável, com hub por
projeto e wikilinks entre as notas.

| Skill | O que faz |
|---|---|
| `/obsidian-docs` | Cria, atualiza e acha doc no vault. É a do dia a dia. |
| `/obsidian-docs-update` | Migra a doc de **um** projeto pro vault, por cópia (o repo fica intocado). |
| `/obsidian-docs-update-all` | Mesma migração, no workspace inteiro. Usa o agent `vault-migrador`. |

Estrutura mantida no vault: `Home.md` global → `<projeto>/<projeto>.md` (hub) → `Specs/`,
`Arquitetura/`, `Bugs/`, `Evolucoes/`, `Analises/`. Toda nota tem frontmatter
(`projeto`, `tipo`, `status`, `data`) e é indexada no hub.

## Instalação

```bash
git clone https://github.com/macrex/obsidian-docs.git ~/repos/obsidian-docs

for s in obsidian-docs obsidian-docs-update obsidian-docs-update-all; do
  ln -s ~/repos/obsidian-docs/$s ~/.claude/skills/$s
done
ln -s ~/repos/obsidian-docs/agents/vault-migrador.md ~/.claude/agents/vault-migrador.md
```

Windows: `New-Item -ItemType SymbolicLink -Path ... -Target ...` (precisa de admin ou Modo de
Desenvolvedor). Copiar as pastas também funciona — só não atualiza com `git pull`.

**Diga onde fica o vault** — sem isso as skills param e perguntam (nunca inventam caminho).
Aponte para a pasta *de projetos* dentro do vault:

```bash
export OBSIDIAN_VAULT="$HOME/obsidian/projetos"     # ~/.zshrc, ~/.bashrc
```

Linter opcional — checa frontmatter, links quebrados e notas órfãs:

```bash
mkdir -p "$OBSIDIAN_VAULT/.scripts"
cp ~/repos/obsidian-docs/scripts/validar_vault.py "$OBSIDIAN_VAULT/.scripts/"
python "$OBSIDIAN_VAULT/.scripts/validar_vault.py" --resumo
```

## CLAUDE.md

As skills só entram sozinhas se o roteamento estiver no seu `CLAUDE.md`. O mínimo:

```markdown
# obsidian-docs
- Vault de documentação: variável `OBSIDIAN_VAULT` (ou `<caminho>/obsidian/projetos`).
- Todo artefato .md de documentação (spec, plano, design, bug, evolução, ADR, arquitetura,
  análise, pesquisa, relatório) → invocar a skill `obsidian-docs` e salvar no vault, NUNCA no
  repo do projeto. Ler doc antiga: mesma skill, on-demand.
- Atualizar doc existente: editar a nota direto no vault (in-place), nunca recriar no repo.
- Migração pro vault é CÓPIA, nunca recorte: proibido apagar ou mover arquivo do repo.
```

Opcionais, na ordem do que mais muda o resultado:

```markdown
- **O vault é a memória dos projetos.** Antes de mexer no código, verifique se existe
  `<vault>/<nome-da-pasta-do-repo>/` e leia ao menos o hub e a nota mais recente de
  `Evolucoes/` — repetir caminho já provado errado custa a sessão.
- **Ao fechar uma leva/versão: registrar a evolução em `Evolucoes/`** e indexar no hub. Uma
  nota por leva, com verificação e pendências. (É o que alimenta a regra acima.)
- Migrar docs pro vault em lote: `obsidian-docs-update` (um projeto) ou
  `obsidian-docs-update-all` (workspace inteiro).
- Vault versionado: commit + `pull --rebase` + push automáticos ao editar nota, sem pedir —
  exceção restrita a esse repo.
- Specs/planos de brainstorming (superpowers) também vão pro vault.
- Rodou o graphify → atualizar `Mapa do Codigo <projeto>.md` no vault. `graphify-out/` fica
  local e no `.gitignore`, nunca no vault.
- Projeto mencionado que não está no cwd → resolver pelo catálogo `<vault>/Home.md` antes de agir.
```

## Notas

- Funciona com o Obsidian fechado: as skills escrevem no filesystem, sem MCP e sem plugin.
- A migração em lote sempre mostra `arquivo → destino → tipo` e **espera confirmação** antes de
  escrever. Nada é apagado do repo — um `.md` pode ser código operacional (instrução de build,
  nota dentro de lib vendorizada) e o classificador não sabe.
- `README`, `CLAUDE.md`, `AGENTS.md`, `SKILL.md`, `LICENSE` e configs nunca são migrados.

MIT — veja [LICENSE](LICENSE).
