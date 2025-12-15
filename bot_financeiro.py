import logging
import os
import psycopg2
from datetime import datetime, date, timedelta
from dotenv import load_dotenv # type: ignore
from telegram import Update # type: ignore
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler, ConversationHandler, CallbackQueryHandler # type: ignore
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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

# --- ESTADOS (Fluxo Novo Gasto e Consulta) ---
(
    # Fluxo Novo Gasto
    ASK_VALOR,
    ASK_CATEGORIA,
    ASK_CATEGORIA_CUSTOM,
    ASK_PAGAMENTO,
    ASK_PAGAMENTO_CUSTOM,
    ASK_NECESSIDADE,
    
    # Fluxo Consulta
    SELECT_PERIOD,
    ASK_START_DATE_MANUAL,
    ASK_END_DATE_MANUAL,
    SELECT_REPORT_TYPE
) = range(10)

# --- CONFIGURAÇÕES DE BOTÕES (Opções padrão) ---
CATEGORIAS_PADRAO = ["Mercado", "Alimentação", "Transporte", "Lazer", "Saúde", "Casa", "Outro"]
PAGAMENTOS_PADRAO = ["Pix", "Crédito", "Débito", "Dinheiro", "VR/VA", "Outro"]

# --- FUNÇÕES DE BANCO DE DADOS ---
def db_connect():
    return psycopg2.connect(**DB_CONFIG)

def salvar_gasto_db(user_id, valor, categoria, pagamento, necessidade):
    conn = db_connect()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO gastos (user_id, valor, categoria, forma_pagamento, necessidade, data_registro)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (user_id, valor, categoria, pagamento, necessidade))
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar: {e}")
        return False
    finally:
        conn.close()

def get_relatorio_agrupado(user_id, start_date, end_date, group_by_field):
    """
    Retorna os gastos agrupados e somados (ex: Total por Categoria).
    group_by_field deve ser 'categoria' ou 'forma_pagamento'
    """
    conn = db_connect()
    try:
        cursor = conn.cursor()
        # Query dinâmica para agrupar
        query = f"""
            SELECT {group_by_field}, SUM(valor) 
            FROM gastos 
            WHERE user_id = %s AND data_registro::date BETWEEN %s AND %s
            GROUP BY {group_by_field}
            ORDER BY SUM(valor) DESC
        """
        cursor.execute(query, (user_id, start_date, end_date))
        resultados = cursor.fetchall() # Retorna lista de tuplas (Nome, ValorTotal)
        cursor.close()
        return resultados
    except Exception as e:
        logging.error(f"Erro no relatorio agrupado: {e}")
        return []
    finally:
        conn.close()

def get_extrato_detalhado(user_id, start_date, end_date):
    conn = db_connect()
    try:
        cursor = conn.cursor()
        query = """
            SELECT valor, categoria, forma_pagamento, data_registro 
            FROM gastos 
            WHERE user_id = %s AND data_registro::date BETWEEN %s AND %s
            ORDER BY data_registro DESC
        """
        cursor.execute(query, (user_id, start_date, end_date))
        return cursor.fetchall()
    except Exception as e:
        logging.error(f"Erro no extrato: {e}")
        return []
    finally:
        conn.close()

def get_total_periodo(user_id, start_date, end_date):
    conn = db_connect()
    try:
        cursor = conn.cursor()
        query = "SELECT SUM(valor) FROM gastos WHERE user_id = %s AND data_registro::date BETWEEN %s AND %s"
        cursor.execute(query, (user_id, start_date, end_date))
        res = cursor.fetchone()
        return res[0] if res and res[0] else 0.0
    finally:
        conn.close()

# --- HELPER: FORMATADORES ---
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_date_flexible(date_str):
    for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    raise ValueError

# --- COMANDOS INICIAIS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**Guarda Din Bot**\n\n"
        "Comandos disponíveis:\n"
        "/novo - Cadastrar gasto (Rápido)\n"
        "/consultar - Relatórios e Extratos\n"
        "/cancelar - Cancelar operação atual\n\n"
        "Use o menu ou digite o comando.",
        parse_mode='Markdown'
    )

# ==============================================================================
# FLUXO 1: CADASTRO DE GASTO (/novo) - ESTILO WHATSAPP (Histórico Limpo)
# ==============================================================================

async def novo_gasto_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Digite o **valor** do gasto (ex: 15,90):", parse_mode='Markdown')
    return ASK_VALOR

async def receive_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor_txt = update.message.text.replace(',', '.')
        valor = float(valor_txt)
        context.user_data['novo_valor'] = valor
        
        # Gera teclado de categorias
        keyboard = [
            [InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in CATEGORIAS_PADRAO
        ]
        # Ajusta layout se precisar (aqui lista vertical simples funciona bem)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(f"Selecione a **Categoria**:", reply_markup=reply_markup, parse_mode='Markdown')
        return ASK_CATEGORIA
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite apenas números (ex: 10.50).")
        return ASK_VALOR

async def receive_category_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.replace("cat_", "")

    if data == "Outro":
        # Edita mensagem anterior removendo botões
        await query.edit_message_text(f"Categoria: Outro")
        # Envia nova pergunta
        await query.message.reply_text("Digite o nome da categoria:")
        return ASK_CATEGORIA_CUSTOM
    
    context.user_data['novo_categoria'] = data
    
    # 1. Congela a escolha anterior (transforma botões em texto)
    await query.edit_message_text(f"Categoria: {data}")
    
    # 2. Chama próxima etapa (que enviará NOVA mensagem)
    return await ask_payment_method(query.message, data)

async def receive_category_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categoria = update.message.text
    context.user_data['novo_categoria'] = categoria
    return await ask_payment_method(update.message, categoria)

async def ask_payment_method(message_obj, categoria_anterior):
    # Botões em 2 colunas
    keyboard = [[InlineKeyboardButton(pag, callback_data=f"pag_{pag}")] for pag in PAGAMENTOS_PADRAO]
    keyboard_layout = [keyboard[i][0] for i in range(len(keyboard))] # Flat list
    # Reorganizando em pares
    it = iter(keyboard_layout)
    keyboard_final = list(zip(it, it))
    # Se sobrar um impar, adiciona no final
    if len(keyboard_layout) % 2 != 0:
        keyboard_final.append((keyboard_layout[-1],))
    
    reply_markup = InlineKeyboardMarkup(keyboard_final)
    
    # Envia NOVA mensagem
    await message_obj.reply_text(
        f"Qual a **Forma de Pagamento** para {categoria_anterior}?", 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )
    return ASK_PAGAMENTO

async def receive_payment_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.replace("pag_", "")

    if data == "Outro":
        await query.edit_message_text(f"Pagamento: Outro")
        await query.message.reply_text("Digite a forma de pagamento:")
        return ASK_PAGAMENTO_CUSTOM

    context.user_data['novo_pagamento'] = data
    
    # 1. Congela escolha anterior
    await query.edit_message_text(f"Pagamento: {data}")
    
    # 2. Próximo passo
    return await ask_necessity(query.message, data)

async def receive_payment_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pagamento = update.message.text
    context.user_data['novo_pagamento'] = pagamento
    return await ask_necessity(update.message, pagamento)

async def ask_necessity(message_obj, pagamento_anterior):
    keyboard = [[InlineKeyboardButton("Sim (Essencial)", callback_data="nec_s"), InlineKeyboardButton("Não (Supérfluo)", callback_data="nec_n")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message_obj.reply_text(
        f"É um gasto **Essencial**?", 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )
    return ASK_NECESSIDADE

async def receive_necessity_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    necessidade = query.data.replace("nec_", "")
    nec_text = "Essencial" if necessidade == 's' else "Supérfluo"
    
    # Congela a pergunta de necessidade
    await query.edit_message_text(f"Necessidade: {nec_text}")

    user_id = query.from_user.id
    valor = context.user_data['novo_valor']
    cat = context.user_data['novo_categoria']
    pag = context.user_data['novo_pagamento']
    
    if salvar_gasto_db(user_id, valor, cat, pag, necessidade):
        msg = (
            f"**Gasto Salvo!**\n"
            f"{formatar_moeda(valor)} em {cat} ({pag})"
        )
        # Envia confirmação final
        await query.message.reply_text(msg, parse_mode='Markdown')
    else:
        await query.message.reply_text("Erro ao salvar no banco de dados.")
    
    return ConversationHandler.END

# ==============================================================================
# FLUXO 2: CONSULTA (/consultar) - ESTILO WHATSAPP
# ==============================================================================

async def consultar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Hoje", callback_data='period_today'), InlineKeyboardButton("Ontem", callback_data='period_yesterday')],
        [InlineKeyboardButton("Este Mês", callback_data='period_curr_month'), InlineKeyboardButton("Mês Passado", callback_data='period_last_month')],
        [InlineKeyboardButton("Outra Data", callback_data='period_custom')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("**Período da consulta:**", reply_markup=reply_markup, parse_mode='Markdown')
    return SELECT_PERIOD

async def handle_period_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    
    today = date.today()
    start = end = None
    label = ""

    if choice == 'period_today':
        start = end = today
        label = "Hoje"
    elif choice == 'period_yesterday':
        start = end = today - timedelta(days=1)
        label = "Ontem"
    elif choice == 'period_curr_month':
        start = today.replace(day=1)
        end = today
        label = "Este Mês"
    elif choice == 'period_last_month':
        first_curr = today.replace(day=1)
        end = first_curr - timedelta(days=1)
        start = end.replace(day=1)
        label = "Mês Passado"
    elif choice == 'period_custom':
        await query.edit_message_text("Período: Personalizado")
        await query.message.reply_text("Digite a data inicial (DD/MM/AAAA):")
        return ASK_START_DATE_MANUAL

    context.user_data['q_start'] = start
    context.user_data['q_end'] = end
    context.user_data['q_label'] = label
    
    # 1. Congela a escolha na mensagem antiga
    await query.edit_message_text(f"Período: {label}")
    
    # 2. Envia nova mensagem com opções
    return await show_report_options(query.message, label)

async def receive_start_date_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dt = parse_date_flexible(update.message.text)
        context.user_data['q_start'] = dt
        await update.message.reply_text("Digite a data final (ou 'ok' para ser igual à inicial):")
        return ASK_END_DATE_MANUAL
    except:
        await update.message.reply_text("Data inválida. Use DD/MM/AAAA.")
        return ASK_START_DATE_MANUAL

async def receive_end_date_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    start = context.user_data['q_start']
    
    if text == 'ok':
        end = start
    else:
        try:
            end = parse_date_flexible(text)
        except:
            await update.message.reply_text("Data inválida.")
            return ASK_END_DATE_MANUAL

    context.user_data['q_end'] = end
    label = f"{start.strftime('%d/%m')} a {end.strftime('%d/%m')}"
    return await show_report_options(update.message, label)

async def show_report_options(message_obj, label_periodo):
    keyboard = [
        [InlineKeyboardButton("Extrato Detalhado", callback_data='view_extrato')],
        [InlineKeyboardButton("Por Categoria", callback_data='view_categoria')],
        [InlineKeyboardButton("Por Pagamento", callback_data='view_pagamento')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message_obj.reply_text(
        f"🔎 O que deseja ver de **{label_periodo}**?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return SELECT_REPORT_TYPE

async def handle_report_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Remove os botões, mostra status carregando
    await query.edit_message_text("Buscando dados...")

    view_type = query.data
    user_id = query.from_user.id
    start = context.user_data['q_start']
    end = context.user_data['q_end']
    
    if view_type == 'view_extrato':
        dados = get_extrato_detalhado(user_id, start, end)
        total = get_total_periodo(user_id, start, end)
        
        if not dados:
            await query.edit_message_text("Nenhum gasto neste período.")
            return ConversationHandler.END
            
        msg = f"**Extrato ({start.strftime('%d/%m')} - {end.strftime('%d/%m')})**\n\n"
        for val, cat, pag, dt in dados:
            msg += f"• {formatar_moeda(val)} ({cat} - {pag})\n"
        msg += f"\n**TOTAL: {formatar_moeda(total)}**"
        
        await query.edit_message_text(msg, parse_mode='Markdown')
        
    elif view_type == 'view_categoria':
        dados = get_relatorio_agrupado(user_id, start, end, 'categoria')
        
        if not dados:
            await query.edit_message_text("Nenhum gasto neste período.")
            return ConversationHandler.END

        msg = "**Resumo por Categoria:**\n\n"
        total_geral = 0
        for cat, val in dados:
            msg += f"▫️ **{cat}:** {formatar_moeda(val)}\n"
            total_geral += val
        msg += f"\n**Total Geral:** {formatar_moeda(total_geral)}"
        
        await query.edit_message_text(msg, parse_mode='Markdown')

    elif view_type == 'view_pagamento':
        dados = get_relatorio_agrupado(user_id, start, end, 'forma_pagamento')
        
        if not dados:
            await query.edit_message_text("Nenhum gasto neste período.")
            return ConversationHandler.END

        msg = "**Resumo por Pagamento:**\n\n"
        total_geral = 0
        for pag, val in dados:
            msg += f"▫️ **{pag}:** {formatar_moeda(val)}\n"
            total_geral += val
        msg += f"\n**Total Geral:** {formatar_moeda(total_geral)}"
        
        await query.edit_message_text(msg, parse_mode='Markdown')
        
    return ConversationHandler.END

async def cancel_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operação cancelada.")
    context.user_data.clear()
    return ConversationHandler.END

# --- MAIN ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Handler Cadastro
    novo_handler = ConversationHandler(
        entry_points=[CommandHandler("novo", novo_gasto_start)],
        states={
            ASK_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_valor)],
            ASK_CATEGORIA: [CallbackQueryHandler(receive_category_button)],
            ASK_CATEGORIA_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_category_custom)],
            ASK_PAGAMENTO: [CallbackQueryHandler(receive_payment_button)],
            ASK_PAGAMENTO_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_payment_custom)],
            ASK_NECESSIDADE: [CallbackQueryHandler(receive_necessity_and_save)]
        },
        fallbacks=[CommandHandler("cancelar", cancel_op)]
    )

    # Handler Consulta
    consultar_handler = ConversationHandler(
        entry_points=[CommandHandler("consultar", consultar_start)],
        states={
            SELECT_PERIOD: [CallbackQueryHandler(handle_period_select)],
            ASK_START_DATE_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_start_date_manual)],
            ASK_END_DATE_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_end_date_manual)],
            SELECT_REPORT_TYPE: [CallbackQueryHandler(handle_report_view)],
        },
        fallbacks=[CommandHandler("cancelar", cancel_op)]
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(novo_handler)
    app.add_handler(consultar_handler)

    print("Bot Guarda Din rodando...")
    app.run_polling()