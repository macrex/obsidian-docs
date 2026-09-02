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

## 3. Projeto no vault

- `visao_geral` lista os projetos que existem. Hub existente **ganha** — nunca duplique
  (`pagamentos-repo` pertence ao hub `pagamentos`).
- Projeto novo de verdade → a primeira `salvar_nota` leva `descricao_projeto` (1 linha) e
  `repo` (caminho local); o servidor cria hub, registra no `Home.md` e só as pastas que as
  notas pedirem.
- Conjunto de tickets/tarefas derivados de um mesmo artefato → `artefato=<nome da nota de
  origem>` em cada `salvar_nota`: vai para `Specs/Tickets - <artefato>/`, nunca solto em
  `Specs/` (regra na skill `obsidian-docs`).

## 4. Copiar

Uma `salvar_nota` por arquivo confirmado:

1. `data` = primeiro commit do arquivo
   (`git log --follow --format=%ad --date=short -- <arquivo> | tail -1`); sem git, omita (hoje).
2. `titulo` = título do documento (o nome vira `YYYY-MM-DD <titulo>.md`); `tipo` da tabela.
3. `corpo` = conteúdo original preservado. Adicione `[[wikilinks]]` para notas relacionadas da
   mesma migração (bug → spec que originou, evolução → bug que resolveu); o link do hub o
   servidor põe.
4. `resumo` = 1 linha para o hub.

Vault git: o servidor commita e empurra a cada nota — não rode git no vault.

## 5. Checagem graphify (só se o projeto usa graphify)

- `graphify-out/` existe? Garanta que está no `.gitignore` e **não** está commitado
  (`git ls-files graphify-out` vazio).
- `graphify-out/` **NUNCA vai pro vault** — é grafo de código, local.
- Lixo antigo de graphify→Obsidian (nota por arquivo de código, dump `.md` de AST) achado no
  repo ou no vault: listar e propor exclusão.
- Mapa curado do código no vault = fluxo "Mapa do Codigo" da skill `obsidian-docs`, sob
  demanda — fora da migração automática.

## 7. Relatório final

N arquivos copiados por tipo, hub criado ou reusado, o que ficou de fora e por quê, pendências
(itens excluídos pelo usuário, gravações que o servidor recusou). Lembrete: daqui em diante doc
nova/atualização é direto no vault (`obsidian-docs`).
