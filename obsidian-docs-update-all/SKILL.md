---
name: obsidian-docs-update-all
description: >
  Migracao da documentacao do WORKSPACE INTEIRO (todos os projetos) pro vault
  Obsidian, por COPIA — repos intocados. Rodar na raiz do workspace, a pasta
  que contem os projetos. Use quando: migrar todos os projetos, varrer o
  workspace. Dispara com: /obsidian-docs-update-all.
---

# obsidian-docs-update-all — migração do workspace inteiro pro vault

# Versao: 2

`$VAULT`: resolva pela ordem da skill `obsidian-docs` — variável de ambiente `OBSIDIAN_VAULT`,
senão o caminho declarado no `CLAUDE.md`, senão pergunte. Nunca invente. Vault é repo git
(`git -C "$VAULT" rev-parse --is-inside-work-tree`)? Então `git -C "$VAULT" pull --rebase
--autostash` antes de ler ou escrever; não é → pule todo passo de git desta skill.

## Papel

Orquestra a migração em massa: descobre os projetos do diretório atual,
inventaria tudo, confirma com o usuário UMA vez e migra projeto a projeto
pro vault. As regras de classificação/padronização são as da skill
`obsidian-docs-update` (um projeto); esta skill só escala para N projetos.

## Fluxo

### 1. Descobrir projetos

No diretório atual (raiz do workspace), listar subpastas de 1º nível que
sejam projeto: têm `.git`, ou manifesto (`package.json`, `pom.xml`,
`pyproject.toml`, `go.mod`, `Cargo.toml`), ou `CLAUDE.md`/`AGENTS.md`.
Ignorar: `node_modules`, `.git`, pastas de vault/Obsidian, `tmp`, `dist`,
`target`. Mostrar a lista detectada antes de inventariar.

### 2. Inventário em paralelo (subagents, read-only)

Um subagent **`vault-migrador`** por projeto, em **modo inventário** (nunca
move nada nesta fase) — pode disparar TODOS os projetos de uma vez (o
runtime enfileira o excedente). Cada um devolve a tabela compacta
`arquivo → destino no vault → tipo` seguindo as regras da
`obsidian-docs-update` (nunca README/CLAUDE.md/SKILL.md/LICENSE/configs).
Projetos sem nada a migrar voltam "limpo".

**REGRA DE MODELO (obrigatória):** os subagents NUNCA herdam o modelo da
sessão principal — trabalho mecânico não justifica o custo. Use sempre um
modelo barato e fixo:
- **Claude Code**: o agent type `vault-migrador` já traz `model: sonnet`;
  use SEMPRE `subagent_type: vault-migrador`. Sem o agent type instalado →
  `general-purpose` com `model: sonnet` explícito. Jamais spawn sem model
  definido. Modelo maior só se o Sonnet comprovadamente não der conta.
- **Outras plataformas**: o modelo rápido/barato equivalente da plataforma.

### 3. GATE único (obrigatório)

Mostrar o inventário agregado: por projeto, contagem por tipo + tabela dos
arquivos. Avisar que TUDO listado será **copiado** pro vault (os repos ficam
intocados). Usuário confirma, exclui projetos ou itens. Sem confirmação,
nada é copiado.

### 4. Migrar (sequencial, um projeto por vez)

Vault versionado é git — **NUNCA migrar dois projetos em paralelo**
(conflito de push/rebase). Para cada projeto confirmado, na ordem:
subagent `vault-migrador` em **modo migração** com a lista confirmada
(mesma regra de modelo do passo 2, nunca o modelo da sessão).
Ele aplica o fluxo da `obsidian-docs-update`: estrutura no vault (reusa se
existir), **copiar** + frontmatter (data do 1º commit) + wikilinks + hub +
`Home.md`, checagem graphify (`graphify-out/` no `.gitignore`, fora do
index), commit do vault com `pull --rebase` antes e push.

**O repo do projeto NUNCA é tocado**: migração é cópia, nunca recorte. Sem
`git rm`, sem apagar, sem commit no projeto.

### 5. Relatório final

Agregado: N projetos migrados, M arquivos por tipo, o que ficou e por quê,
falhas/pendências. Lembrete: daqui em diante doc nova é direto no vault
(`obsidian-docs`).
