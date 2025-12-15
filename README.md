# 🤖 Guarda Din Bot

Um bot do Telegram simples para registrar e acompanhar seus gastos diários. Facilite o controle financeiro diretamente do seu aplicativo de mensagens favorito!

## ✨ Funcionalidades

- **Registro de Gastos:** Salve rapidamente seus gastos com valor, categoria, forma de pagamento e necessidade.
- **Mensagem de Boas-Vindas:** Guia o usuário sobre como interagir com o bot.
- **Consulta por Categoria:** Visualize todos os gastos de uma categoria específica.
- **Consulta por Necessidade:** Filtre gastos entre essenciais ('s') e não essenciais ('n').
- **Consulta Detalhada (por Período, Categoria, Meio de Pagamento, Necessidade):** Um fluxo interativo com botões para filtrar seus gastos.
- **Total de Gastos:** Soma todos os gastos registrados pelo usuário.
- **Integração com PostgreSQL:** Armazena todos os dados em um banco de dados PostgreSQL.
- **Interface Intuitiva:** Interaja com o bot usando um formato de mensagem simples e direto.

## 🚀 Como Começar

Siga os passos abaixo para configurar e rodar o bot em sua máquina.

### Pré-requisitos

Certifique-se de ter o seguinte instalado:

- **Python 3.8+**
- **Docker** (para rodar o PostgreSQL facilmente)
- **uv** (gerenciador de pacotes Python, similar ao `pip` e `venv`)

### 1. Clonar o Repositório

```bash
git clone https://github.com/seu-usuario/guarda-din-bot.git
cd guarda-din-bot
```

### 2. Configurar o Bot do Telegram

1.  Abra o Telegram e procure por `@BotFather`.
2.  Envie o comando `/newbot` para criar um novo bot.
3.  Siga as instruções para dar um nome e um username ao seu bot.
4.  O BotFather lhe fornecerá um **Token de API**. Guarde-o, pois ele será necessário na próxima etapa.

### 3. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto (na mesma pasta de `bot_financeiro.py`) com as seguintes variáveis:

```
TELEGRAM_TOKEN=SEU_TOKEN_DO_TELEGRAM
DB_NAME=guarda_din_bot
DB_USER=admin
DB_PASSWORD=sua_senha_segura
DB_HOST=localhost
DB_PORT=5432
```

**Importante:** Substitua `SEU_TOKEN_DO_TELEGRAM` pelo token que você obteve do BotFather e `sua_senha_segura` por uma senha forte para o seu banco de dados.

### 4. Configurar o Banco de Dados PostgreSQL

Vamos usar o Docker para iniciar uma instância do PostgreSQL.

1.  **Iniciar o contêiner PostgreSQL:**

    ```bash
    docker run --name postgres -e POSTGRES_PASSWORD=sua_senha_segura -e POSTGRES_USER=admin -e POSTGRES_DB=guarda_din_bot -p 5432:5432 -d postgres
    ```
    **Nota:** Certifique-se de que `sua_senha_segura`, `admin` e `guarda_din_bot` correspondam aos valores definidos no seu arquivo `.env`.

2.  **Conectar ao banco de dados e criar a tabela:**

    ```bash
    docker exec -it postgres psql -U admin -d guarda_din_bot
    ```
    Dentro do console `psql`, execute o seguinte comando para criar a tabela `gastos`:

    ```sql
    CREATE TABLE gastos (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL, -- Adicionado para identificar o usuário
        valor DECIMAL(10, 2) NOT NULL,
        categoria VARCHAR(50),
        forma_pagamento VARCHAR(50),
        necessidade CHAR(1),
        data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ```
    Para sair do console `psql`, digite `\q`.

### 5. Instalar Dependências e Rodar o Bot

Com o `uv` instalado, você pode instalar as dependências e iniciar o bot:

```bash
uv sync
uv run python bot_financeiro.py
```

Você deverá ver a mensagem: `🤖 Bot rodando e escutando...`

## 💬 Como Usar o Bot

Envie mensagens para o seu bot do Telegram no seguinte formato:

```
gasto: 50.00, categoria: mercado, forma de pagamento: débito, necessidade: s
```

**Exemplo:**

- `gasto: 120.50, categoria: restaurante, forma de pagamento: credito, necessidade: n`
- `gasto: 35.00, categoria: transporte, forma de pagamento: pix, necessidade: s`

O bot responderá confirmando o registro do gasto ou informando sobre um formato inválido.
