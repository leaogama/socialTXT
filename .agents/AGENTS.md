# Regras do Workspace (SocialTXT)

- **Fluxo de Versionamento Seguro (Git & GitHub):**
  - Sempre que uma tarefa for concluída e validada/testada com sucesso, verifique o `git status`.
  - Garanta que nenhum arquivo sensível (incluindo `.env`, `cookies.txt`, chaves de API, tokens, senhas, credenciais, arquivos temporários, caches ou dumps) seja adicionado ou enviado ao repositório.
  - Faça o commit local das alterações validadas com uma mensagem objetiva e em português.
  - Execute o `git push origin main` para enviar as atualizações.

- **Validação Pré-Commit:**
  - Antes de criar qualquer commit ou fazer push, verifique se o aplicativo compila/constrói com sucesso e se os testes/build disponíveis passam sem erros.
  - Se houver qualquer falha em testes, build, commit ou push, interrompa imediatamente a execução e avise o usuário.

- **Restrições de Controle de Versão:**
  - Nunca utilize comandos destrutivos ou de reescrita de histórico (como `git push --force`, `git reset --hard`, `git clean -fd`, `git rebase` ou similares) sem a autorização explícita do usuário.
