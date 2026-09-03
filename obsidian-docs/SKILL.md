---
name: obsidian-docs
description: >
  Vault Obsidian de documentacao — doc nasce no vault, nao no repo. Use ao
  criar, salvar ou ler doc de qualquer projeto: spec, plano, design, bug,
  evolucao, ADR, arquitetura, analise, pesquisa, relatorio; achar doc antiga;
  atualizar Mapa do Codigo. Dispara com: /obsidian-docs, documentar.
---

# obsidian-docs — documentação de projetos no Obsidian

# Versao: 10

Todo acesso ao vault é pelo MCP `vault-docs` (`mcp/servidor_vault.py` deste repo). Ele sabe
onde o vault fica e aplica as convenções — pasta por tipo, nome com data, frontmatter, link e
entrada no hub, `Home.md`, commit → `pull --rebase` → push. Você decide **o quê** documentar
e escreve o conteúdo; ele cuida do **como**. Estrutura: `Home.md` → `<projeto>/<projeto>.md`
(hub) → pastas por tipo; toda nota linka o hub e está listada nele.

**NUNCA** Read/Grep/Glob/Write/Edit direto nos arquivos do vault, nem `git` nele. Sem as
ferramentas `mcp__vault-docs__*` na sessão → pare: registrar o servidor
(`python <repo>/mcp/servidor_vault.py --instalar`, ver README) ou, se `claude mcp list` já o
mostra, reiniciar o Claude Code — sessão aberta antes do registro não o carrega.

## Ferramentas

| Ferramenta | Uso |
|---|---|
| `visao_geral` | projetos existentes, contagem por tipo, notas recentes — primeiro passo quando não sabe o nome do projeto |
| `buscar` | full-text sem acento/caixa; filtros `projeto`, `tipo`, `status` |
| `listar_notas` | metadados, mais recentes primeiro (última evolução: `projeto=X tipo=evolucao limite=1`) |
| `ler_nota` | conteúdo integral, por caminho ou nome de wikilink |
| `conexoes` | wikilinks de saída e backlinks |
| `salvar_nota` | nota nova — faz pasta, nome, frontmatter, link e entrada no hub, hub/Home novos, git |
| `atualizar_nota` | nota existente — corpo, status, tags, resumo do hub ou sucessora (obsoleta), git |
| `mapa_codigo` | mapa do código do projeto a partir do `graphify-out/` do repo (frescor, comunidades, god nodes) — leia antes de mexer no código |
| `consultar_codigo` | pergunta de arquitetura ao grafo: `pergunta`, `explicar=<nó>` ou `caminho=[A, B]` |
| `gerar_mapa` | regrava `Mapa do Codigo <projeto>` do grafo, preservando `## Leitura curada` (ou recebendo `leitura`) |

## Regra dura

- Todo artefato `.md` de documentação vai para o vault via `salvar_nota`. NUNCA criar doc no
  repo do projeto, NUNCA commitar doc lá. Ficam no repo: `CLAUDE.md`, `AGENTS.md`, `SKILL.md`,
  `README.md`, configs — arquivos operacionais que ferramentas leem em lugar fixo.
- Doc existente que muda → `atualizar_nota` na própria nota (in-place). Nunca recriar no repo,
  nunca cópia local.
- Projeto = nome da pasta do repo git, minúsculo, sem acento. **Hub existente sempre ganha**:
  na primeira gravação da sessão num projeto, `visao_geral` (ou `ler_nota <projeto>`) para não
  duplicar — repo `pagamentos-repo` pertence ao hub `pagamentos` que já existe. Projeto novo de
  verdade → `salvar_nota` com `descricao_projeto` (1 linha) e `repo` (caminho local).

## Salvar: o que você passa

`salvar_nota(projeto, tipo, titulo, corpo, resumo, …)`:

- `tipo` → pasta: `spec`/`plano` → `Specs/`; `bug` → `Bugs/`; `evolucao` → `Evolucoes/`;
  `arquitetura`/`adr` → `Arquitetura/`; `analise` (pesquisa, estudo, relatório, review) →
  `Analises/`; `mapa` → `Mapa do Codigo <projeto>.md` na raiz do projeto (regrava).
- `titulo`: curto, acento permitido. A nota vira `YYYY-MM-DD <titulo>.md` (hoje, ou `data`).
- `corpo`: markdown. Vá direto ao conteúdo — o servidor põe `# titulo` e `Projeto: [[projeto]]`
  se faltarem. Linke notas relacionadas por `[[nome da nota]]` (só o nome, nunca a pasta): spec
  que originou o bug, evolução que resolveu, nota anterior. O grafo do Obsidian nasce daí.
- `resumo`: 1 linha — é a entrada da nota no hub.
- `status`: `rascunho` (proposta) | `ativo` (padrão) | `resolvido` | `obsoleto`.
  `tags`: 1-3, kebab-case sem acento, opcional.
- `arquivos`: caminhos tocados pela leva (`git diff --name-only`), relativos ao repo. O servidor
  anexa `## Componentes tocados` (nós por comunidade, link ao Mapa) a partir do grafo do
  graphify. Passe sempre em evolução, bug e spec de mudança.
- **Ticket** de um artefato (quebra de spec/plano em tarefas, inclusive por skills externas como
  `to-tickets`): `tipo=plano` + `artefato=<nome da nota de origem>`. Vai para
  `Specs/Tickets - <artefato>/`, nunca solto em `Specs/` — muitas notas de uma vez afogam o
  artefato que as gerou.

## Lifecycle (`atualizar_nota`)

- Concluiu o que a nota descreve (plano executado, bug corrigido) → `status=resolvido` na hora.
- Doc substituída por outra → `sucessora=<nome da nova nota>` (fica `obsoleto`, link no topo).
- `rascunho` → `status=ativo` quando aprovada.

## Evolução (fechar leva/versão)

Uma nota `tipo=evolucao` por leva e por projeto: o que mudou, por quê, tentativas que falharam,
como foi verificado, pendências. Mesmo tema e arquivos da última evolução
(`listar_notas projeto=X tipo=evolucao limite=1`) → `atualizar_nota` nela, não nota nova.

## Ler / achar: duas fontes, cada pergunta tem a sua

O vault sabe o que foi **decidido e escrito**; o grafo do graphify sabe o que o código **é
agora**. Vá primeiro na fonte da coluna da esquerda:

| A pergunta é sobre | Fonte primária | Como |
|---|---|---|
| por que é assim, o que já foi descartado, o que a leva mudou | vault | `ler_nota`, `buscar`, `listar_notas`, `conexoes` |
| estrutura do código: quem chama X, caminho de A a B, o que é gargalo | grafo | `consultar_codigo`, `mapa_codigo` |
| onde mexer num projeto que você não conhece | as duas | hub + última evolução + `mapa_codigo` |

Sem grafo no projeto, as ferramentas de código dizem isso e o vault segue sozinho — graphify é
opcional, nada depende dele. NUNCA carregar o vault inteiro no contexto.

## Mapa do Codigo (só se o projeto usa graphify)

`graphify-out/` fica no repo, no `.gitignore` e fora do index (`git ls-files graphify-out`
vazio; se rastreado, `git rm -r --cached graphify-out`) — nunca no vault. O servidor chega nele
pela linha `Repo:` do hub; hub sem ela → passe `repo=` uma vez e o servidor registra.

Após cada rodada do graphify, sem o usuário pedir (e sob demanda):
`gerar_mapa(projeto, leitura=<sua prosa>)`. O servidor põe comunidades, god nodes e destaques
do GRAPH_REPORT; a `leitura` é a parte curada — domínios, o que vale saber, lacunas — e é
preservada quando você não a passa. Continua PROIBIDO: dump bruto, nota por arquivo de código.

## Migração de docs existentes

Só quando o usuário pedir: skill irmã `obsidian-docs-update` (um projeto) ou
`obsidian-docs-update-all` (workspace). Lá a migração é **cópia** — o repo nunca perde arquivo.
