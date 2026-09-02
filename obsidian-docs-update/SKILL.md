---
name: obsidian-docs-update
description: >
  Migracao em lote da documentacao de UM projeto pro vault Obsidian, por COPIA
  — o repo do projeto fica intocado. Use quando: migrar docs, levar
  documentacao pro vault, importar docs antigas.
  Dispara com: /obsidian-docs-update.
---

# obsidian-docs-update — migração de docs do projeto pro vault

# Versao: 6

O vault é acessado só pelo MCP `vault-docs` (skill `obsidian-docs`): `salvar_nota` grava cada
arquivo com pasta, frontmatter, hub, `Home.md` e git. Sem as ferramentas `mcp__vault-docs__*`
na sessão → pare e peça para registrar o servidor (README).

Faxina/importação em lote: leva toda a documentação de um projeto pro vault. Roda DENTRO do
projeto, uma vez (ou quando acumular sujeira). O dia a dia — criar/ler doc nova — é da skill
`obsidian-docs`.

Depois da migração vale a regra permanente: doc gerada ou atualizada daqui em diante nasce
**direto no vault**, nunca mais no repo.

## REGRA DURA — migração é CÓPIA, nunca recorte

**PROIBIDO apagar qualquer arquivo do repo do projeto.** A nota nasce no vault e o original
**fica onde está**. Nada de `git rm`, nada de mover, nada de commit `docs: migrados para o
vault Obsidian` — esse commit não pode ser gerado em projeto nenhum.

Motivo: remoção automática já apagou centenas de arquivos em dezenas de repos, incluindo
arquivos que só *pareciam* documentação mas eram parte funcional do código — um
`LEIA-MODIFICADO.txt` dentro de uma lib vendorizada, registros de modificação de dependência,
instruções de build. Um `.md` no repo pode ser código operacional; o classificador não sabe.

Única exceção, e só quando `graphify-out/` estiver rastreado: `git rm -r --cached graphify-out`
(tira do index, mantém em disco) + `.gitignore`. Nunca apaga do disco, nunca toca em outro arquivo.

## Fluxo

Detalhe de cada passo (o que varrer, o que nunca migrar, formato do plano, padronização):
`references/procedimento.md`.

1. **Inventário** — varrer o repo atrás de doc; nunca incluir arquivo operacional
   (`README`, `CLAUDE.md`, `SKILL.md`, configs).
2. **Plano de migração — GATE OBRIGATÓRIO**: tabela `arquivo → destino → tipo` ao usuário.
   **Aguarde confirmação**; ele pode excluir itens.
3. **Projeto no vault** — `visao_geral`: hub existente ganha; projeto novo de verdade →
   `descricao_projeto` e `repo` na primeira `salvar_nota`.
4. **Copiar** — uma `salvar_nota` por arquivo confirmado: `data` do 1º commit, conteúdo
   original como `corpo`, `resumo` de 1 linha, wikilinks entre notas relacionadas.
5. **Checagem graphify** (só se o projeto usa) — `graphify-out/` no `.gitignore` e fora do
   index; nunca vai pro vault.
6. **Repo do projeto — NÃO TOCAR** (regra dura acima).
7. **Relatório final** — o que foi copiado, o que ficou de fora e por quê.
