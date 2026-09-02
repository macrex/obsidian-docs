---
name: obsidian-docs
description: >
  Vault Obsidian de documentacao — doc nasce no vault, nao no repo. Use ao
  criar, salvar ou ler doc de qualquer projeto: spec, plano, design, bug,
  evolucao, ADR, arquitetura, analise, pesquisa, relatorio; achar doc antiga;
  atualizar Mapa do Codigo. Dispara com: /obsidian-docs, documentar.
---

# obsidian-docs — documentação de projetos no Obsidian

# Versao: 6

## `$VAULT` — resolver ANTES de qualquer leitura ou escrita

`$VAULT` é a pasta de projetos dentro do vault Obsidian. Aparece em toda esta skill e nas irmãs
`obsidian-docs-update` / `obsidian-docs-update-all`. Ordem de resolução:

1. Variável de ambiente `OBSIDIAN_VAULT` (cheque com `echo "$OBSIDIAN_VAULT"`) — se existir,
   é ela. Recomendado: resolve sozinha máquinas diferentes, Windows e macOS/Linux, sem editar
   a skill.
2. Caminho declarado no `CLAUDE.md` (global ou do projeto) do usuário.
3. Nenhum dos dois → **pergunte ao usuário** e peça para registrar em (1) ou (2).

**NUNCA invente o caminho, nunca escreva fora dele.** Nos exemplos abaixo os caminhos usam `/`;
no Windows o separador é `\`.

### Sincronização (só se o vault for um repo git)

Muita gente versiona o vault e o compartilha entre máquinas. Detecte:

```bash
git -C "$VAULT" rev-parse --is-inside-work-tree
```

Deu certo → rode `git -C "$VAULT" pull --rebase --autostash` na primeira vez que a sessão tocar
o vault e de novo antes de cada edição. Sem isso você lê versão velha e o push quebra em
conflito. O `--autostash` não é opcional: o Obsidian reescreve `.obsidian/graph.json` sozinho e
o `pull --rebase` puro aborta. Não é repo git → pule todo passo de git desta skill.

Detalhe de cada fluxo (salvar passo a passo, template de hub, lifecycle de status, ler/achar
doc, Mapa do Codigo, comandos de commit): `references/fluxos.md`. Abra antes de escrever.

## Regra dura

- Todo artefato `.md` de documentação vai para o vault `$VAULT`. NUNCA criar doc
  no repo do projeto, NUNCA commitar doc lá.
- Gerar, atualizar ou regravar doc existente → editar a nota DIRETAMENTE no vault (in-place).
  Nunca recriar no repo, nunca manter cópia local.
- Ficam no repo do projeto (fora desta skill): `CLAUDE.md`, `AGENTS.md`, `SKILL.md`,
  `README.md`, configs — arquivos operacionais que ferramentas leem em lugar fixo.
- Escrita por filesystem direto (Write/Edit). Sem MCP, sem plugin; Obsidian não precisa estar aberto.
- **Nenhuma nota nasce órfã**: toda nota tem o link do hub (`Projeto: [[<projeto>]]`) no corpo E
  uma entrada no hub. Sem os dois ela some do grafo. Wikilink usa só o NOME da nota
  (`[[2026-07-25 Titulo]]`) — caminho com pasta (`[[projeto/2026-07-25 Titulo]]`) quebra.

## Estrutura do vault

```
$VAULT/
  Home.md                       ← hub global: wikilink p/ cada projeto
  <projeto>/
    <projeto>.md                ← hub do projeto (nó central no graph)
    Mapa do Codigo <projeto>.md ← curada, gerada do graphify-out (opcional, pós-graphify)
    Specs/                      ← specs + planos + designs
      Tickets - <artefato>/     ← os tickets derivados DAQUELE artefato (ver abaixo)
    Arquitetura/                ← ADRs, domínio, docs de arquitetura
    Bugs/
    Evolucoes/
    Analises/                   ← pesquisas, estudos, relatórios avulsos
```

- Nome do projeto = nome da pasta do repo git. Minúsculo, sem acento.
- Pastas de tipo criadas SOB DEMANDA, só quando o primeiro artefato daquele tipo aparecer.

## Tickets sempre em pasta própria (regra dura)

Quebrar um artefato (spec, plano, design) em tickets gera MUITAS notas de uma vez.
Soltas em `Specs/` elas afogam o artefato que as originou — o problema real que esta
regra resolve.

- Tickets NUNCA ficam soltos em `Specs/`. Vão para `Specs/Tickets - <nome do artefato>/`,
  onde `<nome do artefato>` é o nome do arquivo da nota que os originou, SEM `.md`.
- Uma pasta por artefato. Todos os tickets daquela quebra vão para a MESMA pasta;
  outro artefato ganha a sua.
- A pasta nasce junto com o primeiro ticket, nunca antes.
- Vale para qualquer quebra em tickets/tarefas, inclusive a das skills externas
  (`to-tickets` e afins): o destino é decidido aqui, não por elas.

Exemplo:

```
Specs/
  2026-08-25 Indexacao da trilha de auditoria.md          ← o artefato
  Tickets - 2026-08-25 Indexacao da trilha de auditoria/  ← a pasta dos tickets dele
    2026-08-25 Ticket 01 Tracer da pipeline.md
    2026-08-25 Ticket 02 Carga inicial.md
```

Wikilink usa só o NOME da nota, então mover ticket para a pasta não quebra link nenhum —
nem os do hub, nem os entre tickets.

## Salvar artefato (resumo)

1. **Detectar projeto** — hub existente sempre ganha; nunca duplicar projeto.
2. **Bootstrap** do hub e da pasta de tipo, se faltarem.
3. **Classificar tipo** → pasta (spec/plano→`Specs`, adr→`Arquitetura`, bug→`Bugs`,
   evolucao→`Evolucoes`, analise→`Analises`, mapa→raiz). **Ticket de um artefato →
   `Specs/Tickets - <nome do artefato>/`** (ver regra acima).
4. **Escrever** `YYYY-MM-DD <titulo>.md` com frontmatter obrigatório e wikilinks.
5. **Atualizar o hub** e rodar o linter, se instalado (`$VAULT/.scripts/validar_vault.py`).
6. **Commit → `pull --rebase` → push**, nessa ordem — só se o vault for repo git.

## Migração de docs existentes

Só quando o usuário pedir, e é da skill irmã **`obsidian-docs-update`** (`/obsidian-docs-update`):
varrer o projeto, inventariar, copiar, padronizar, indexar. Lá a migração é
**cópia** — o repo do projeto nunca perde arquivo.
