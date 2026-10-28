import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Importar as funções da base de dados modularizada
from db import (
    init_db, guardar_jogo, obter_jogo, registar_clique,
    processar_resultado_jogo, obter_dados_lista,
    confirmar_pagamento_por_ref, obter_estatisticas_globais
)

# Servidor web para o Render
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

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
MBWAY_NUMBER = os.environ.get("MBWAY_NUMBER", "O teu número MB Way")
ADMIN_ID = os.environ.get("ADMIN_ID")

if not TOKEN:
    raise ValueError("A variável de ambiente TELEGRAM_BOT_TOKEN não está definida.")

bot = telebot.TeleBot(TOKEN)

# Inicializar BD ao arrancar
init_db()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🤖 O bot do **BetOverTwo** está operacional com arquitetura modularizada.", parse_mode="Markdown")

@bot.message_handler(commands=['publicar'])
def publicar_prognostico(message):
    if ADMIN_ID and str(message.from_user.id) != str(ADMIN_ID):
        return

    texto_args = message.text.replace("/publicar", "").strip()
    parts = [p.strip() for p in texto_args.split("|")]
    
    if len(parts) < 4:
        bot.reply_to(message, "⚠️ **Uso incorreto!** Formato:\n`/publicar J1 | Equipas | DD/MM/AAAA HH:MM | Odd`", parse_mode="Markdown")
        return
    
    jogo_id, equipas, data_hora_str, odd = parts[0].upper(), parts[1], parts[2], parts[3]
    
    try:
        data_hora_obj = datetime.strptime(data_hora_str, "%d/%m/%Y %H:%M")
    except ValueError:
        bot.reply_to(message, "⚠️ Formato de data inválido! Usa: `DD/MM/AAAA HH:MM`", parse_mode="Markdown")
        return

    guardar_jogo(jogo_id, equipas, data_hora_str, data_hora_obj, odd)

    texto_canal = (
        f"⚽ **BetOverTwo - Prognóstico {jogo_id}**\n\n"
        f"📅 **Data e Hora:** {data_hora_str}\n"
        "🎯 **Mercado:** Ambas Marcam & +2.5 Golos\n"
        "📉 **Odd Mínima:** > 1.75\n\n"
        "🔒 *Jogo Oculto - Clica abaixo para desbloquear gratuitamente.*"
    )
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"🔓 Desbloquear Grátis ({jogo_id})", callback_data=f"desbloquear_{jogo_id}"))
    
    destino = CHANNEL_ID if CHANNEL_ID else message.chat.id
    bot.send_message(destino, texto_canal, parse_mode="Markdown", reply_markup=markup)
    bot.reply_to(message, f"✅ Prognóstico `{jogo_id}` publicado no canal!", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("desbloquear_"))
def callback_desbloquear(call):
    jogo_id = call.data.replace("desbloquear_", "")
    jogo = obter_jogo(jogo_id)
    
    if not jogo:
        bot.answer_callback_query(call.id, "❌ Jogo não encontrado.", show_alert=True)
        return

    data_hora_obj = datetime.strptime(jogo["data_hora_obj"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() >= data_hora_obj:
        bot.answer_callback_query(call.id, "❌ Este prognóstico já expirou!", show_alert=True)
        return

    user_id = call.from_user.id
    user_name = call.from_user.first_name or "Utilizador"
    
    registar_clique(jogo_id, user_id, user_name)

    texto_privado = (
        f"🔓 **Prognóstico Desbloqueado ({jogo_id})**\n\n"
        f"⚽ **Equipas:** {jogo['equipas']}\n"
        f"🎯 **Mercado:** Ambas Marcam & +2.5 Golos\n"
        f"📉 **Odd:** `{jogo['odd']}`\n\n"
        "📌 *Nota:* Assumes o compromisso de honrar **2€ via MB Way** apenas se der **Green**."
    )

    try:
        bot.send_message(user_id, texto_privado, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "Detalhes enviados em privado!")
    except Exception:
        bot.answer_callback_query(call.id, "Inicia primeiro chat privado com o bot.", show_alert=True)

@bot.message_handler(commands=['resultado'])
def registar_resultado(message):
    if ADMIN_ID and str(message.from_user.id) != str(ADMIN_ID):
        return

    parts = [p.strip() for p in message.text.replace("/resultado", "").split("|")]
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Formato: `/resultado J1 | 2-1 | Green`", parse_mode="Markdown")
        return
    
    jogo_id, placar, res = parts[0].upper(), parts[1], parts[2].capitalize()
    
    if res not in ["Green", "Red"]:
        bot.reply_to(message, "⚠️ O estado tem de ser `Green` ou `Red`.", parse_mode="Markdown")
        return

    resultado_processamento = processar_resultado_jogo(jogo_id, res)
    if not resultado_processamento:
        bot.reply_to(message, f"❌ Jogo `{jogo_id}` não encontrado.", parse_mode="Markdown")
        return

    emoji = "✅🟢" if res == "Green" else "❌🔴"
    texto_res = (
        f"📊 **Resultado Final ({jogo_id})**\n\n"
        f"⚽ **Equipas:** {resultado_processamento['equipas']}\n"
        f"📌 **Placar:** {placar}\n"
        f"📉 **Odd:** `{resultado_processamento['odd']}`\n"
        f"👉 **Status:** {emoji} **{res.upper()}**"
    )
    
    destino = CHANNEL_ID if CHANNEL_ID else message.chat.id
    bot.send_message(destino, texto_res, parse_mode="Markdown")

    if res == "Green":
        for u_id, ref_codigo in resultado_processamento['cobrancas']:
            msg_cobranca = (
                f"🎉 O Jogo **{jogo_id}** deu **GREEN!** 🟢\n\n"
                f"Efetua o pagamento de **2€** via MB Way (`{MBWAY_NUMBER}`).\n"
                f"🔑 **Referência:** `{ref_codigo}` (Prazo: 24h)"
            )
            try:
                bot.send_message(u_id, msg_cobranca, parse_mode="Markdown")
            except Exception:
                pass
        bot.reply_to(message, f"✅ Green registado para `{jogo_id}` e cobranças enviadas!", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"✅ Red registado para `{jogo_id}`.", parse_mode="Markdown")

@bot.message_handler(commands=['lista'])
def ver_lista_jogo(message):
    if ADMIN_ID and str(message.from_user.id) != str(ADMIN_ID):
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Uso correto: `/lista [ID]` (ex: `/lista J1`)", parse_mode="Markdown")
        return
        
    jogo_id = args[1].upper()
    dados = obter_dados_lista(jogo_id)
    
    if not dados:
        bot.reply_to(message, f"❌ Jogo `{jogo_id}` não encontrado.")
        return

    jogo, participantes = dados
    pendentes = [p for p in participantes if p["estado_pagamento"] == 'Pendente']
    pagos = [p for p in participantes if p["estado_pagamento"] == 'Pago']
    
    texto = (
        f"📊 **Estado do Jogo: {jogo_id}**\n"
        f"⚽ *{jogo['equipas']}* (Odd: `{jogo['odd']}` | Status: **{jogo['status']}**)\n\n"
        f"⏳ **Pendentes ({len(pendentes)}):**\n"
    )
    for p in pendentes:
        texto += f"• `Ref: {p['ref_codigo']}` — **{p['user_name']}**\n"
        
    texto += f"\n✅ **Pagos ({len(pagos)}):**\n"
    for p in pagos:
        texto += f"• `Ref: {p['ref_codigo']}` — **{p['user_name']}**\n"
        
    bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(commands=['pago'])
def confirmar_pagamento(message):
    if ADMIN_ID and str(message.from_user.id) != str(ADMIN_ID):
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Uso correto: `/pago [Referência]` (ex: `/pago J1-4821`)", parse_mode="Markdown")
        return
        
    ref = args[1].upper()
    resultado = confirmar_pagamento_por_ref(ref)
    
    if not resultado:
        bot.reply_to(message, f"❌ Referência `{ref}` não encontrada.")
        return
        
    if resultado["status"] == "ja_pago":
        bot.reply_to(message, f"⚠️ A referência `{ref}` já constava como paga.")
        return
        
    bot.reply_to(message, f"✅ Pagamento `{ref}` ({resultado['user_name']}) confirmado!", parse_mode="Markdown")
    try:
        bot.send_message(resultado['user_id'], f"✅ O teu pagamento para o jogo **{resultado['jogo_id']}** foi validado!", parse_mode="Markdown")
    except Exception:
        pass

@bot.message_handler(commands=['stats'])
def ver_estatisticas(message):
    pub, greens, reds = obter_estatisticas_globais()
    total = greens + reds
    win_rate = (greens / total * 100) if total > 0 else 0
    
    texto_stats = (
        "📊 **Estatísticas Oficiais - BetOverTwo**\n\n"
        f"• Prognósticos Publicados: `{pub}`\n"
        f"• Greens: `{greens} 🟢`\n"
        f"• Reds: `{reds} ❌`\n"
        f"• **Win Rate Real:** `{win_rate:.1f}%`\n"
        "📉 **Odd Média:** `> 1.75` (Garantido)"
    )
    bot.reply_to(message, texto_stats, parse_mode="Markdown")

if __name__ == "__main__":
    print("Bot modularizado a iniciar polling...")
    bot.infinity_polling()
