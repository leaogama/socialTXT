# SocialTXT 🎬📝

O **SocialTXT** é um microsserviço local e plataforma web para extração de transcrições e resumos inteligentes de conteúdos de redes sociais. Ele suporta links do **YouTube, TikTok, Instagram Reels** e postagens do **X (Twitter)**.

---

## ✨ Funcionalidades Principais

*   **Interface Premium:** Design escuro com efeito de vidro (glassmorphism), totalmente responsivo e com micro-animações.
*   **Gerenciador de Diretrizes (Prompts):** 
    *   Crie, edite, duplique e exclua diretrizes personalizadas para a IA.
    *   Reordenação de diretrizes usando arrastar e soltar (Drag-and-Drop).
    *   Importação e Exportação de diretrizes em arquivos `.json`.
    *   Toggle para forçar o formato estruturado JSON ou permitir respostas livres em texto puro.
    *   Pré-visualização em tempo real (Live Preview) do prompt final do sistema.
*   **API REST:** FastAPI autogerada com documentação interativa Swagger.
*   **Servidor MCP (Model Context Protocol):** Conecte o app como ferramenta nativa de resumo no Claude Desktop ou Cursor.
*   **Preparado para VPS:** Arquitetura em containers Docker ideal para implantação com Portainer.

---

## 🛠️ Tecnologias Utilizadas

*   **Backend:** Python, FastAPI, Playwright (para burlar restrições e capturar requisições de mídia), `yt-dlp` (para download/extração de áudios), `youtube-transcript-api` (para obter legendas prontas) e `faster-whisper` (para transcrição local de áudio).
*   **Frontend:** HTML5, CSS3 clássico (Vanilla), JavaScript moderno (ES6+).
*   **IA:** Suporte flexível a OpenRouter, DeepSeek API e OpenAI.

---

## 🚀 Como Rodar Localmente (Docker)

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/leaogama/socialTXT.git
    cd socialTXT
    ```

2.  **Configure as variáveis de ambiente:**
    Copie o arquivo de exemplo e preencha sua chave de IA:
    ```bash
    cp .env.example .env
    ```
    Edite o arquivo `.env` inserindo sua `LLM_API_KEY`.

3.  **Inicie os containers:**
    ```bash
    docker compose up -d --build
    ```

4.  **Acesse no seu navegador:**
    *   **Interface Web:** [http://localhost:8001](http://localhost:8001)
    *   **Documentação da API:** [http://localhost:8001/docs](http://localhost:8001/docs)

---

## 🔌 Integração & API

### 1. Chamada HTTP REST
O app expõe o endpoint `POST /api/summarize` para integração com automações (Make, n8n, scripts, etc.):

```bash
curl -X POST "http://localhost:8001/api/summarize" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://youtube.com/shorts/vPhwZcuThsc",
       "detail": "normal",
       "language": "pt-BR"
     }'
```

### 2. Servidor MCP (Model Context Protocol)
Integre o resumo de mídias sociais diretamente no Claude Desktop ou Cursor. 

Adicione a configuração no arquivo `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "socialtxt": {
      "command": "python",
      "args": ["C:/_git/socialTXT/mcp_server.py"],
      "env": {
        "LLM_API_KEY": "SUA_API_KEY_AQUI"
      }
    }
  }
}
```

---

## 🧠 Arquitetura de IA & Casos de Uso (Ex: Integração com WhatsApp Bots)

O SocialTXT funciona como um **pipeline de processamento de mídia** desacoplado:
1. **Ingestão:** Captura o áudio/vídeo via Playwright e `yt-dlp`.
2. **Transcrição local (Whisper):** Transcreve o áudio em texto corrido com pontuação inteligente.
3. **Refinamento LLM (DeepSeek/OpenRouter):** Condensa o texto, extrai pontos chave e formata as respostas no padrão JSON.

### Exemplo de Integração: Moderadores e Agentes de Vendas no WhatsApp

Você pode conectar a API do SocialTXT ao seu bot de monitoramento de grupos de WhatsApp para criar automações inteligentes baseadas em mídias compartilhadas:

#### 🛡️ Modo Moderador Automático
Evite que vídeos com golpes, spam, links de afiliados de jogos de azar ou conteúdos nocivos inundem o grupo:
* O bot captura a URL do Reels/TikTok/YouTube postada no chat.
* Dispara uma chamada para o SocialTXT com um prompt crítico temporário (`prompt_override`):
  *"Analise se o conteúdo deste vídeo promove fraudes financeiras, golpes, conteúdo adulto ou discursos de ódio. Retorne true ou false na chave 'proibido'."*
* Se a API responder que é proibido, o bot deleta a mensagem do grupo imediatamente.

#### 📈 Modo Vendas Contextual (Marketing de Atração)
Aproveite os vídeos que as próprias pessoas enviam para ofertar seus produtos com base no assunto real do vídeo:
* Um membro envia um vídeo sobre produtividade.
* O bot chama o SocialTXT solicitando o resumo e instruindo o modelo a conectá-lo ao seu SaaS de gestão.
* O bot envia uma mensagem natural: *"Muito legal esse vídeo que o @Membro compartilhou! O Ponto 2 abordado é sobre perda de foco, e o nosso software resolve exatamente isso. Quem quiser conhecer: [Link]"*.

#### 📰 Daily Digest (Resumo Diário do Grupo)
O bot coleta todos os links enviados no grupo durante o dia, solicita o resumo estruturado e, à noite, posta um boletim geral no grupo consolidando o melhor do dia de forma limpa e organizada.

---

## 🐳 Implantação em VPS com Portainer

O SocialTXT funciona no modelo GitOps através do Portainer.

1.  Crie uma nova **Stack** no Portainer.
2.  Selecione o método de build **Repository** e aponte para este repositório do GitHub.
3.  Configure as variáveis de ambiente (`LLM_API_KEY`, etc.) diretamente na interface de variáveis do Portainer por segurança.
4.  Clique em **Deploy the stack**.
5.  Para atualizar o app após novos commits, basta abrir a stack no Portainer e clicar em **"Pull and Redeploy"**.

---

## ⚙️ Regras do Projeto (`.agents/AGENTS.md`)
O repositório possui regras específicas de qualidade e controle de versão seguras localizadas na pasta `.agents/AGENTS.md`. Nossos agentes automáticos analisam esse arquivo para garantir validações pré-commit e impedir o vazamento de chaves ou arquivos sensíveis.
