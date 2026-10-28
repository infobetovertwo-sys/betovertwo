import os
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# 1. Servidor web para manter o Render ativo (Obrigatório para Web Service)
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"BetOverTwo Bot is alive and running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

web_thread = threading.Thread(target=run_web_server, daemon=True)
web_thread.start()

# 2. Configuração do Bot e Variáveis de Ambiente
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
MBWAY_NUMBER = os.environ.get("MBWAY_NUMBER", "O teu número MB Way")
ADMIN_ID = os.environ.get("ADMIN_ID") # O teu ID pessoal do Telegram para receber os avisos

if not TOKEN:
    raise ValueError("A variável de ambiente TELEGRAM_BOT_TOKEN não está definida.")

bot = telebot.TeleBot(TOKEN)

# Memória temporária para gerir os pedidos pendentes (código -> user_id)
pedidos_pendentes = {}

# 3. Comando Inicial
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🤖 O bot do **BetOverTwo** está operacional e pronto para gerir os prognósticos e pagamentos.")

# 4. Publicar Prognóstico com Botão de Desbloqueio (Para o canal ou teste)
@bot.message_handler(commands=['publicar'])
def publicar_prognostico(message):
    texto_prognostico = (
        "⚽ **BetOverTwo - Prognóstico em Destaque**\n\n"
        "⚔️ Jogo: [Exemplo: Equipa A vs Equipa B]\n"
        "🎯 Mercado: Ambas Marcam & +2.5 Golos\n\n"
        "🔒 *Este prognóstico está bloqueado.*\n"
        "📉 Odd:\n"
        "• [Conteúdo Protegido]"
    )
    
    # Criar o botão interativo para desbloquear
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔓 Desbloquear por 2€ (MB Way)", callback_data="desbloquear_prognostico"))
    
    # Enviar para o canal se configurado, senão responde no chat atual
    destino = CHANNEL_ID if CHANNEL_ID else message.chat.id
    bot.send_message(destino, texto_prognostico, parse_mode="Markdown", reply_markup=markup)
    
    if CHANNEL_ID and message.chat.id != int(CHANNEL_ID):
        bot.reply_to(message, "✅ Prognóstico publicado com sucesso no canal!")

# 5. Interação quando o utilizador clica no botão do canal
@bot.callback_query_handler(func=lambda call: call.data == "desbloquear_prognostico")
def callback_desbloquear(call):
    user_id = call.from_user.id
    user_name = call.from_user.first_name or "Utilizador"
    
    # Gerar um código único de 4 dígitos para referência do pagamento
    codigo_ref = str(random.randint(1000, 9999))
    pedidos_pendentes[codigo_ref] = user_id
    
    # Mensagem enviada ao utilizador em privado / chat
    texto_instrucoes = (
        f"💳 **Passos para Desbloquear o Prognóstico**\n\n"
        f"1. Efetue um pagamento de **2€** via MB Way para o número: `{MBWAY_NUMBER}`\n"
        f"2. Insira o seguinte código na descrição/mensagem (se possível) ou guarde-o:\n"
        f"🔑 **Código de Referência:** `{codigo_ref}`\n\n"
        f"Assim que o pagamento for verificado pelo administrador, receberá o acesso automaticamente!"
    )
    
    try:
        bot.send_message(user_id, texto_instrucoes, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "Verifique as suas mensagens privadas para concluir o pagamento.")
    except Exception:
        bot.answer_callback_query(call.id, "Por favor, inicie primeiro uma conversa privada com o bot (clique no nome do bot e em 'Iniciar').", show_alert=True)
        return

    # Notificação enviada para ti (Administrador)
    if ADMIN_ID:
        texto_admin = (
            f"🔔 **Novo Pedido de Desbloqueio!**\n\n"
            f"👤 Utilizador: {user_name} (ID: `{user_id}`)\n"
            f"🔑 Código Atribuído: `{codigo_ref}`\n\n"
            f"Vai à tua app MB Way confirmar a entrada e aprova com:\n"
            f"`/aprovar {codigo_ref}`"
        )
        bot.send_message(ADMIN_ID, texto_admin, parse_mode="Markdown")

# 6. Comando de Aprovação do Admin (`/aprovar CÓDIGO`)
@bot.message_handler(commands=['aprovar'])
def aprovar_pagamento(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Uso correto: `/aprovar [código_de_referência]`", parse_mode="Markdown")
        return
    
    codigo_ref = args[1]
    
    if codigo_ref in pedidos_pendentes:
        user_id = pedidos_pendentes[codigo_ref]
        
        # Conteúdo completo do prognóstico desbloqueado
        prognostico_completo = (
            "🎉 **Pagamento Confirmado! Aqui tem o seu prognóstico:**\n\n"
            "⚽ Jogo: [Exemplo: Equipa A vs Equipa B]\n"
            "🎯 Mercado: Ambas Marcam & +2.5 Golos\n"
            "📉 **Odd Final:** `1.95`\n"
            "📊 Análise detalhada: Excelente valor estatístico para este mercado com base nas últimas jornadas."
        )
        
        # Enviar o prognóstico desbloqueado em privado ao utilizador
        bot.send_message(user_id, prognostico_completo, parse_mode="Markdown")
        bot.reply_to(message, f"✅ Pagamento com o código `{codigo_ref}` aprovado com sucesso para o utilizador `{user_id}`!", parse_mode="Markdown")
        
        # Remover o pedido da lista pendente
        del pedidos_pendentes[codigo_ref]
    else:
        bot.reply_to(message, "❌ Código de referência inválido ou já expirado/aprovado.")

if __name__ == "__main__":
    print("Bot a iniciar o polling...")
    bot.infinity_polling()
