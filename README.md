# obsidian-docs — movido para macrex/skills

Este repositório foi **descontinuado**. As três skills e o servidor MCP `vault-docs` agora vivem
em **[macrex/skills](https://github.com/macrex/skills)**, junto com as outras skills, e é de lá
que se instala:

```bash
npx skills add https://github.com/macrex/skills -g --skill obsidian-docs --skill obsidian-docs-update --skill obsidian-docs-update-all
```

O motivo da mudança: o CLI de skills copia **só a pasta da skill**, então um servidor MCP que
mora fora dela nunca é instalado junto. No repositório novo, o `servidor_vault.py` viaja dentro
da `obsidian-docs`, em `scripts/`, com os testes e o linter do vault ao lado dele e o agent
`vault-migrador` em `assets/` — uma instalação resolve tudo. As instruções de registro do
servidor, a tabela de ferramentas, a parte do graphify e o roteamento de `CLAUDE.md` estão no
README de lá.

O código que existia aqui continua no histórico deste repositório.

MIT — veja [LICENSE](LICENSE).
