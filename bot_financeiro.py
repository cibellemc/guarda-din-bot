import logging
import os
import psycopg2
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') 

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT')
}

# --- LOGS ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- FUNÇÕES DE BANCO DE DADOS ---
def salvar_gasto(dados):
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        query = """
            INSERT INTO gastos (valor, categoria, forma_pagamento, necessidade)
            VALUES (%s, %s, %s, %s)
        """
        # Converte o valor para float, substituindo vírgula por ponto se necessário
        valor_limpo = float(dados['gasto'].replace(',', '.'))
        
        cursor.execute(query, (
            valor_limpo, 
            dados['categoria'], 
            dados['forma de pagamento'], 
            dados['necessidade']
        ))
        
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        logging.error(f"Erro no banco: {e}")
        return False
    finally:
        if conn is not None:
            conn.close()

# --- PARSER DE TEXTO ---
def interpretar_mensagem(texto):
    """
    Transforma string 'gasto: 10, categoria: x...' em dicionário
    """
    try:
        # Divide por vírgula
        itens = texto.split(',')
        dados = {}
        
        for item in itens:
            if ':' in item:
                chave, valor = item.split(':', 1)
                dados[chave.strip().lower()] = valor.strip()
        
        # Verifica se tem todos os campos
        campos_obrigatorios = ['gasto', 'categoria', 'forma de pagamento', 'necessidade']
        if all(k in dados for k in campos_obrigatorios):
            return dados
        return None
    except Exception:
        return None

# --- HANDLER DO TELEGRAM ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_usuario = update.message.text
    logging.info(f"Recebido: {texto_usuario}")

    dados = interpretar_mensagem(texto_usuario)

    if dados:
        sucesso = salvar_gasto(dados)
        if sucesso:
            await update.message.reply_text(
                f"✅ **Gasto Salvo!**\n"
                f"💰 Valor: R$ {dados['gasto']}\n"
                f"🏷️ Categoria: {dados['categoria']}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Erro ao salvar no banco. Verifique os logs.")
    else:
        await update.message.reply_text(
            "⚠️ **Formato Inválido**\n\n"
            "Envie assim:\n"
            "`gasto: 50.00, categoria: mercado, forma de pagamento: débito, necessidade: s`",
            parse_mode='Markdown'
        )

# --- EXECUÇÃO ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Adiciona o handler para mensagens de texto (ignora comandos que começam com /)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🤖 Bot rodando e escutando...")
    app.run_polling()