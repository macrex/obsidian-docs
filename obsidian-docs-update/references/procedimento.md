# Migração em lote — detalhe de cada passo

## 1. Inventário

Varra o repo atual atrás de candidatos:

- `Glob **/*.md` + `Glob **/*.txt` de anotação (ex.: `notas.txt`, `todo.txt`)
- Alvos típicos: `docs/`, `doc/`, `documentation/`, `docs/superpowers/specs|plans/`,
  `docs/history/` (iteration-N), specs/planos/análises soltos na raiz, `ADR*/`,
  `arquitetura*`, relatórios, pesquisas, `*.draft.md`

**NUNCA migrar** (operacional, fica no repo): `README*`, `CLAUDE.md`, `AGENTS.md`,
`GEMINI.md`, `SKILL.md`, `LICENSE*`, `CHANGELOG*`, `CONTRIBUTING*`, `CODE_OF_CONDUCT*`,
templates de `.github/`, configs, qualquer `.md` que ferramenta leia em path fixo.
Na dúvida, pergunte.

## 2. Plano de migração (gate)

Tabela ao usuário, avisando que vai copiar tudo pro vault:

```
| arquivo no repo | → destino no vault | tipo |
|---|---|---|
| docs/history/iteration-1.md | <projeto>/Evolucoes/2026-01-15 Iteration 1.md | evolucao |
| docs/design-x.md            | <projeto>/Specs/2026-03-02 Design X.md       | spec |
```

Aguarde confirmação. O usuário pode excluir itens da lista.

## 3. Estrutura no vault

- `$VAULT/<projeto>/` já existe → **usa** a estrutura que está lá.
- Não existe → cria hub `<projeto>.md` (template da skill `obsidian-docs`), registra
  `[[<projeto>]]` no `Home.md`, e cria só as pastas de tipo que a migração precisa
  (`Specs`, `Arquitetura`, `Bugs`, `Evolucoes`, `Analises`).

## 4. Copiar + padronizar + indexar

Para cada arquivo confirmado:

1. Nome: `YYYY-MM-DD <titulo>.md` — data = primeiro commit do arquivo
   (`git log --follow --format=%ad --date=short -- <arquivo> | tail -1`); sem git, data de hoje.
2. Frontmatter padrão da skill `obsidian-docs` (projeto, tipo, status, data, tags). Conteúdo
   original preservado abaixo do frontmatter.
3. Wikilinks: linkar o hub (`[[<projeto>]]`) e notas relacionadas da mesma migração
   (bug → spec que originou, evolução → bug que resolveu).
4. Indexar: entrada `- [[nota]] — resumo 1 linha` na seção do tipo no hub.

## 5. Checagem graphify (só se o projeto usa graphify)

- `graphify-out/` existe? Garanta que está no `.gitignore` e **não** está commitado
  (`git ls-files graphify-out` vazio).
- `graphify-out/` **NUNCA vai pro vault** — é grafo de código, local.
- Lixo antigo de graphify→Obsidian (nota por arquivo de código, dump `.md` de AST) achado no
  repo ou no vault: listar e propor exclusão.
- Mapa curado do código no vault = fluxo "Mapa do Codigo" da skill `obsidian-docs`, sob
  demanda — fora da migração automática.

## 7. Commit do vault (só se o vault for repo git)

```bash
git -C "$VAULT" add -A
git -C "$VAULT" commit -m "<projeto>: migracao de docs do repo"
git -C "$VAULT" pull --rebase
git -C "$VAULT" push
```

Ordem importa: commit → `pull --rebase` → push (rebase com worktree sujo falha). Push falhou →
`pull --rebase` e re-tenta; persistindo, avisa o usuário e segue (o commit local preserva tudo).

## 8. Relatório final

N arquivos copiados por tipo, hub atualizado, o que ficou de fora e por quê, pendências (itens
excluídos pelo usuário). Lembrete: daqui em diante doc nova/atualização é direto no vault
(`obsidian-docs`).
