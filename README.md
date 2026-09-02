# obsidian-docs

> **Português** · [English](README.en.md)

Skills de [Claude Code](https://claude.com/claude-code) que guardam a documentação dos seus
projetos num vault Obsidian em vez de dentro dos repositórios. **O repo guarda código, o vault
guarda memória**: spec, plano, ADR, bug e nota de evolução viram um grafo navegável, com hub por
projeto e wikilinks entre as notas.

| Peça | O que faz |
|---|---|
| MCP `vault-docs` | O servidor. Lê o vault por busca e grava notas já nas convenções (pasta, nome, frontmatter, hub, git). |
| `/obsidian-docs` | A skill do dia a dia: decide o que documentar, escreve o conteúdo e chama o servidor. |
| `/obsidian-docs-update` | Migra a doc de **um** projeto pro vault, por cópia (o repo fica intocado). |
| `/obsidian-docs-update-all` | Mesma migração, no workspace inteiro. Usa o agent `vault-migrador`. |

Estrutura mantida no vault: `Home.md` global → `<projeto>/<projeto>.md` (hub) → `Specs/`,
`Arquitetura/`, `Bugs/`, `Evolucoes/`, `Analises/`. Toda nota tem frontmatter
(`projeto`, `tipo`, `status`, `data`), linka o hub e é indexada nele — o servidor garante isso
em código, não na memória do modelo.

## Instalação

**1. Clone e ligue as skills** (Windows: `New-Item -ItemType SymbolicLink -Path ... -Target ...`,
ou copie as pastas):

```bash
git clone https://github.com/macrex/obsidian-docs.git ~/repos/obsidian-docs

for s in obsidian-docs obsidian-docs-update obsidian-docs-update-all; do
  ln -s ~/repos/obsidian-docs/$s ~/.claude/skills/$s
done
ln -s ~/repos/obsidian-docs/agents/vault-migrador.md ~/.claude/agents/vault-migrador.md
```

**2. Registre o servidor**, apontando para a pasta *de projetos* dentro do seu vault:

```bash
python ~/repos/obsidian-docs/mcp/servidor_vault.py --instalar --vault ~/obsidian/projetos
```

Só isso. Python 3.9+, sem dependências. O comando registra o servidor no escopo de usuário do
Claude Code — vale em todos os seus projetos — e pode ser repetido à vontade. Se você já tem a
variável `OBSIDIAN_VAULT`, `--vault` é opcional. Vault que é repositório git ganha commit +
`pull --rebase` + push a cada gravação; para desligar, acrescente `--sem-git`.

**3. Reinicie o Claude Code** e confira: `claude mcp list` mostra `vault-docs … ✔ Connected`.

## Ferramentas do servidor

| Ferramenta | O que faz |
|---|---|
| `visao_geral` | Panorama: projetos, contagem por tipo, notas recentes. |
| `buscar` | Full-text sem acento/caixa, filtros `projeto`/`tipo`/`status`, com trecho. |
| `listar_notas` | Caminho + frontmatter, mais recentes primeiro. |
| `ler_nota` | Conteúdo integral, por caminho relativo ou nome de wikilink. |
| `conexoes` | Wikilinks de saída e backlinks — navegação pelo grafo. |
| `salvar_nota` | Nota nova: pasta por tipo, `YYYY-MM-DD titulo.md`, frontmatter, link e entrada no hub, hub/`Home.md` se o projeto for novo, commit+push. Tickets em `Specs/Tickets - <artefato>/`. |
| `atualizar_nota` | Nota existente: corpo, status, tags, resumo no hub ou sucessora (marca obsoleta e linka). |

Autoteste, num vault temporário: `python ~/repos/obsidian-docs/mcp/teste_servidor_vault.py`.

## CLAUDE.md

As skills só entram sozinhas se o roteamento estiver no seu `CLAUDE.md`. O mínimo:

```markdown
# obsidian-docs
- Todo artefato .md de documentação (spec, plano, design, bug, evolução, ADR, arquitetura,
  análise, pesquisa, relatório) → skill `obsidian-docs`, que grava no vault pelo MCP
  `vault-docs` (`salvar_nota`). NUNCA no repo do projeto.
- Ler/achar doc: `buscar`, `ler_nota`, `listar_notas`, `conexoes`, `visao_geral`. Nunca
  Read/Grep/Write/Edit direto nos arquivos do vault, nunca git nele.
- Doc existente que muda → `atualizar_nota` (in-place), nunca recriar no repo.
- Migração pro vault é CÓPIA, nunca recorte: proibido apagar ou mover arquivo do repo.
```

Opcionais, na ordem do que mais muda o resultado:

```markdown
- **O vault é a memória dos projetos.** Antes de mexer no código, leia o hub
  (`ler_nota <nome-da-pasta-do-repo>`) e a nota mais recente de `Evolucoes/`
  (`listar_notas projeto=<projeto> tipo=evolucao limite=1`) — repetir caminho já provado
  errado custa a sessão.
- **Ao fechar uma leva/versão: registrar a evolução** (`salvar_nota tipo=evolucao`). Uma nota
  por leva, com verificação e pendências. (É o que alimenta a regra acima.)
- Migrar docs pro vault em lote: `obsidian-docs-update` (um projeto) ou
  `obsidian-docs-update-all` (workspace inteiro).
- Specs/planos de brainstorming (superpowers) também vão pro vault.
- Rodou o graphify → `salvar_nota tipo=mapa` (`Mapa do Codigo <projeto>`). `graphify-out/`
  fica local e no `.gitignore`, nunca no vault.
- Projeto mencionado que não está no cwd → resolver antes de agir: `ler_nota <projeto>`; nome
  incerto → `buscar <nome>` ou `visao_geral`.
```

## Notas

- Funciona com o Obsidian fechado: é tudo filesystem, sem plugin. O servidor é a única porta
  do vault — assim nenhuma nota nasce órfã, sem frontmatter ou fora do hub.
- Linter opcional do vault inteiro (`scripts/validar_vault.py --resumo`): checa frontmatter,
  links quebrados e notas fora do hub em vaults antigos, anteriores ao servidor.
- A migração em lote sempre mostra `arquivo → destino → tipo` e **espera confirmação** antes de
  escrever. Nada é apagado do repo — um `.md` pode ser código operacional (instrução de build,
  nota dentro de lib vendorizada) e o classificador não sabe.
- `README`, `CLAUDE.md`, `AGENTS.md`, `SKILL.md`, `LICENSE` e configs nunca são migrados.

MIT — veja [LICENSE](LICENSE).
