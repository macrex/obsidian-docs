# obsidian-docs — detalhe dos fluxos

## Salvar artefato (passo a passo)

1. **Detectar projeto**: nome da pasta raiz do repo git atual; não-git → nome da pasta de
   trabalho. Minúsculo, sem acento. ANTES de criar hub novo, conferir se já existe hub
   igual/parecido no vault (`Glob $VAULT/*/*.md`) — hub existente GANHA; NUNCA
   duplicar projeto.
2. **Bootstrap se preciso**:
   - `$VAULT/Home.md` não existe → criar (template abaixo) antes de tudo.
   - `<projeto>/<projeto>.md` não existe → criar hub (template abaixo) e adicionar
     `- [[<projeto>]] — <descrição 1 linha>` na seção `## Projetos` do `Home.md` (ordem alfabética).
   - Pasta do tipo não existe → criar.
3. **Classificar tipo** → pasta:

   | tipo (frontmatter) | pasta |
   |---|---|
   | spec, plano | Specs |
   | plano que é **ticket** de um artefato | `Specs/Tickets - <nome do artefato>/` |
   | arquitetura, adr | Arquitetura |
   | bug | Bugs |
   | evolucao | Evolucoes |
   | analise | Analises |
   | mapa | raiz do projeto (`Mapa do Codigo <projeto>.md`) |

   Tickets NUNCA ficam soltos em `Specs/`: uma quebra gera muitas notas de uma vez e
   afoga o artefato que as originou. `<nome do artefato>` é o nome do arquivo da nota
   de origem, sem `.md`; a pasta nasce com o primeiro ticket. Regra completa no
   `SKILL.md`.

4. **Escrever a nota**: nome `YYYY-MM-DD <titulo>.md` (título pode ter acento; pastas não).
   Frontmatter obrigatório:

   ```yaml
   ---
   projeto: <projeto>
   tipo: spec | plano | bug | evolucao | arquitetura | adr | analise | mapa
   status: rascunho | ativo | resolvido | obsoleto
   data: YYYY-MM-DD
   tags: []
   ---
   ```

   Tags opcionais, poucas (1-3), kebab-case sem acento. Corpo linka o hub
   (`Projeto: [[<projeto>]]`) e notas relacionadas via `[[wikilink]]` — spec que originou o bug,
   evolução que resolveu, etc. O graph do Obsidian nasce desses links.
5. **Atualizar o hub**: `- [[YYYY-MM-DD titulo]] — resumo 1 linha` na seção do tipo (criar
   `## <Tipo>` se não existir). Validar depois com o linter, se instalado (ver abaixo).
6. **Commit + sync** — só se o vault for repo git (`git -C "$VAULT" rev-parse
   --is-inside-work-tree`). Nesta ordem (`pull --rebase` com worktree sujo falha):

   ```bash
   git -C "$VAULT" add -A
   git -C "$VAULT" commit -m "<projeto>: <resumo>"
   git -C "$VAULT" pull --rebase
   git -C "$VAULT" push
   ```

   Outras sessões também escrevem no vault; conflito em hub/`Home.md` → manter as duas
   entradas, são listas. Push falhou → `pull --rebase` e re-tenta; persistindo, avisa o usuário
   e segue (o commit local já preserva tudo). Autoria do próprio usuário, sem trailer de
   assistente/IA.

### Linter (opcional)

```bash
python "$VAULT/.scripts/validar_vault.py" --resumo
```

Checa frontmatter, links quebrados, notas fora do hub e órfãs. Não instalado → pule este passo
(o script vem no repo desta skill, em `scripts/validar_vault.py`; instalação no README). Erro
novo introduzido por você = corrigir antes de commitar.

## Template do `Home.md` (hub global)

Só no bootstrap, quando o vault ainda não tem `Home.md`. Sem o frontmatter o linter acusa E1.

```markdown
---
projeto: vault
tipo: hub
status: ativo
data: YYYY-MM-DD
tags: [hub]
---

# Home

Vault de documentação de todos os projetos. Um hub por projeto abaixo.

## Projetos

- [[<projeto>]] — <descrição de 1 linha>
```

## Template de hub de projeto

```markdown
---
projeto: <projeto>
tipo: hub
status: ativo
data: YYYY-MM-DD
tags: [hub]
---

# <projeto>

<descrição de 1-2 linhas do projeto>. Hub global: [[Home]].
Repo: <path local do repo>
```

## Status das notas (lifecycle)

- Concluiu o trabalho que a nota descreve (plano executado, bug corrigido) → `status: resolvido`
  na hora, na própria nota.
- Doc substituída por outra → `status: obsoleto` + wikilink pra sucessora no topo do corpo.
- `rascunho` → `ativo` quando aprovada/valendo.

## Ler / achar doc

1. Partir do hub: `$VAULT/<projeto>/<projeto>.md` — lista tudo com wikilinks.
2. Navegar wikilink → nota (`[[X]]` = arquivo `X.md` em qualquer pasta do vault).
3. Busca por conteúdo: `Grep` em `$VAULT/<projeto>/` (ou vault inteiro se
   cross-projeto).
4. NUNCA carregar o vault inteiro no contexto. Hub → nota certa, só o necessário.

## Mapa do Codigo (opcional — requer graphify)

Só vale se o projeto usa o graphify (indexador de código em grafo) para indexar o
código. Não usa → não existe Mapa do Codigo; ignore esta seção.

**Quando**: automático após cada rodada do graphify — terminou a indexação, atualize o mapa na
sequência, sem o usuário pedir. Também sob demanda.

1. Ler `graphify-out/GRAPH_REPORT.md` do repo atual (god nodes, comunidades, conexões inferidas,
   lacunas). Ausente → sugerir rodar o graphify primeiro.
2. Escrever/atualizar `<projeto>/Mapa do Codigo <projeto>.md` (tipo `mapa`; nome com o projeto
   para o wikilink ser único no vault): domínios/comunidades, componentes-chave, conexões que
   valem saber, lacunas — CURADO, prosa + listas.
3. **PROIBIDO**: dump bruto do graphify, nota por arquivo de código, listar todo arquivo
   `.py`/`.ts`. Isso polui o vault e mata a navegação; é a razão desta regra. O `graphify-out/`
   em si NUNCA vai pro vault — fica local no projeto.
4. Projeto é git → garantir `graphify-out/` no `.gitignore` e fora do index
   (`git ls-files graphify-out` vazio; se rastreado, `git rm -r --cached graphify-out`).
5. Linkar `[[Mapa do Codigo <projeto>]]` no hub (seção `## Mapa`) e commitar o vault.
