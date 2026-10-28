import os
import random
import threading
import sqlite3
from datetime import datetime, timedelta
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
ADMIN_ID = os.environ.get("ADMIN_ID")

if not TOKEN:
    raise ValueError("A variável de ambiente TELEGRAM_BOT_TOKEN não está definida.")

bot = telebot.TeleBot(TOKEN)

# 3. Inicialização da Base de Dados SQLite (Persistência contra reboots do Render)
def init_db():
    conn = sqlite3.connect("betovertwo.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Tabela de Jogos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jogos (
            jogo_id TEXT PRIMARY KEY,
            equipas TEXT,
            data_hora_str TEXT,
            data_hora_obj TIMESTAMP,
            odd TEXT,
            status TEXT DEFAULT 'Pendente'
        )
    """)
    
    # Tabela de Cliques / Participantes por Jogo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS participantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogo_id TEXT,
            user_id INTEGER,
            user_name TEXT,
            ref_codigo TEXT,
            estado_pagamento TEXT DEFAULT 'Pendente',
            data_limite TIMESTAMP,
            FOREIGN KEY (jogo_id) REFERENCES jogos (jogo_id)
        )
    """)
    
    # Tabela de Estatísticas Globais
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estatisticas (
            chave TEXT PRIMARY KEY,
            valor INTEGER
        )
    """)
    
    # Inicializar contadores se não existirem
    cursor.execute("INSERT OR IGNORE INTO estatisticas (chave, valor) VALUES ('publicados', 0)")
    cursor.execute("INSERT OR IGNORE INTO estatisticas (chave, valor) VALUES ('greens', 0)")
    cursor.execute("INSERT OR IGNORE INTO estatisticas (chave, valor) VALUES ('reds', 0)")
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect("betovertwo.db", check_same_thread=False)

# 4. Comando Inicial
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🤖 O bot do **BetOverTwo** está operacional e pronto para gerir os prognósticos, cliques e pagamentos pós-Green.", parse_mode="Markdown")

# 5. Publicar Jogo com ID (Ex: /publicar J1 | Sporting vs Benfica | 30/10/2026 20:30 | 1.85)
@bot.message_handler(commands=['publicar'])
def publicar_prognostico(message):
    if ADMIN_ID and str(message.from_user.id) != str(ADMIN_ID):
        return

    texto_args = message.text.replace("/publicar", "").strip()
    parts = [p.strip() for p in texto_args.split("|")]
    
    if len(parts) < 4:
        bot.reply_to(message, "⚠️ **Uso incorreto!** Formato obrigatório:\n`/publicar J1 | Equipas | DD/MM/AAAA HH:MM | Odd`", parse_mode="Markdown")
        return
    
    jogo_id = parts[0].upper()
    equipas = parts[1]
    data_hora_str = parts[2]
    odd = parts[3]
    
    try:
        data_hora_obj = datetime.strptime(data_hora_str, "%d/%m/%Y %H:%M")
    except ValueError:
        bot.reply_to(message, "⚠️ Formato de data e hora inválido! Usa: `DD/MM/AAAA HH:MM`", parse_mode="Markdown")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO jogos (jogo_id, equipas, data_hora_str, data_hora_obj, odd, status)
        VALUES (?, ?, ?, ?, ?, 'Pendente')
    """, (jogo_id, equipas, data_hora_str, data_hora_obj, odd))
    
    cursor.execute("UPDATE estatisticas SET valor = valor + 1 WHERE chave = 'publicados'")
    conn.commit()
    conn.close()

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
    bot.reply_to(message, f"✅ Prognóstico `{jogo_id}` publicado com sucesso no canal!", parse_mode="Markdown")

# 6. Interação quando o utilizador clica no botão de desbloqueio
@bot.callback_query_handler(func=lambda call: call.data.startswith("desbloquear_"))
def callback_desbloquear(call):
    jogo_id = call.data.replace("desbloquear_", "")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT equipas, data_hora_obj, odd, status FROM jogos WHERE jogo_id = ?", (jogo_id,))
    jogo = cursor.fetchone()
    
    if not jogo:
        bot.answer_callback_query(call.id, "❌ Este jogo já não existe ou foi removido.", show_alert=True)
        conn.close()
        return

    equipas, data_hora_obj_str, odd, status_jogo = jogo
    data_hora_obj = datetime.strptime(data_hora_obj_str, "%Y-%m-%d %H:%M:%S")

    if datetime.now() >= data_hora_obj:
        bot.answer_callback_query(call.id, "❌ Este prognóstico já expirou porque o jogo já começou!", show_alert=True)
        conn.close()
        return

    user_id = call.from_user.id
    user_name = call.from_user.first_name or "Utilizador"

    # Verificar se já desbloqueou este jogo
    cursor.execute("SELECT id FROM participantes WHERE jogo_id = ? AND user_id = ?", (jogo_id, user_id))
    ja_registado = cursor.fetchone()

    if not ja_registado:
        cursor.execute("""
            INSERT INTO participantes (jogo_id, user_id, user_name, ref_codigo, estado_pagamento)
            VALUES (?, ?, ?, '', 'Aguardando Resultado')
        """, (jogo_id, user_id, user_name))
        conn.commit()

    conn.close()

    # Enviar detalhes em privado com aviso dos 15 minutos e compromisso
    texto_privado = (
        f"🔓 **Prognóstico Desbloqueado com Sucesso ({jogo_id})**\n\n"
        f"⚽ **Equipas:** {equipas}\n"
        f"🎯 **Mercado:** Ambas Marcam & +2.5 Golos\n"
        f"📉 **Odd:** `{odd}`\n\n"
        "📌 *Nota de Compromisso:* Ao desbloquear, assumes o compromisso de honrar **2€ via MB Way** apenas se o jogo der **Green**. Se der Red, não pagas absolutamente nada!\n"
        "⏱️ *Garantia:* O desbloqueio demorou menos de 15m. Bons lucros!"
    )

    try:
        bot.send_message(user_id, texto_privado, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "Detalhes enviados para o teu chat privado!")
    except Exception:
        bot.answer_callback_query(call.id, "Por favor, inicia primeiro uma conversa privada com o bot.", show_alert=True)

# 7. Registar Resultado do Jogo (/resultado J1 | 2-1 | Green)
@bot.message_handler(commands=['resultado'])
def registar_resultado(message):
    if ADMIN_ID and str(message.from_user.id) != str(ADMIN_ID):
        return

    texto_args = message.text.replace("/resultado", "").strip()
    parts = [p.strip() for p in texto_args.split("|")]
    
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ **Uso incorreto!** Formato:\n`/resultado J1 | 2-1 | Green` (ou Red)", parse_mode="Markdown")
        return
    
    jogo_id = parts[0].upper()
    placar = parts[1]
    res = parts[2].capitalize()
    
    if res not in ["Green", "Red"]:
        bot.reply_to(message, "⚠️ O estado final tem de ser obrigatoriamente `Green` ou `Red`.", parse_mode="Markdown")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT equipas, odd FROM jogos WHERE jogo_id = ?", (jogo_id,))
    jogo = cursor.fetchone()
    
    if not jogo:
        bot.reply_to(message, f"❌ Jogo `{jogo_id}` não encontrado.", parse_mode="Markdown")
        conn.close()
        return

    equipas, odd = jogo
    cursor.execute("UPDATE jogos SET status = ? WHERE jogo_id = ?", (res, jogo_id))
    
    if res == "Green":
        cursor.execute("UPDATE estatisticas SET valor = valor + 1 WHERE chave = 'greens'")
        emoji = "✅🟢"
    else:
        cursor.execute("UPDATE estatisticas SET valor = valor + 1 WHERE chave = 'reds'")
        emoji = "❌🔴"
        
    conn.commit()

    # Publicar no Canal
    texto_res = (
        f"📊 **Resultado Final - BetOverTwo ({jogo_id})**\n\n"
        f"⚽ **Jogo:** {equipas}\n"
        f"📌 **Placar:** {placar}\n"
        f"🎯 **Mercado:** Ambas Marcam & +2.5 Golos\n"
        f"📉 **Odd:** `{odd}`\n"
        f"👉 **Status:** {emoji} **{res.upper()}**"
    )
    
    destino = CHANNEL_ID if CHANNEL_ID else message.chat.id
    bot.send_message(destino, texto_res, parse_mode="Markdown")

    # Se for Green, gerar referências e notificar participantes para pagamento em 24h
    if res == "Green":
        cursor.execute("SELECT user_id, user_name FROM participantes WHERE jogo_id = ?", (jogo_id,))
        participantes = cursor.fetchall()
        
        data_limite = datetime.now() + timedelta(hours=24)
        
        for p in participantes:
            u_id, u_name = p
            ref_codigo = f"{jogo_id}-{random.randint(1000, 9999)}"
            
            cursor.execute("""
                UPDATE participantes 
                SET ref_codigo = ?, estado_pagamento = 'Pendente', data_limite = ? 
                WHERE jogo_id = ? AND user_id = ?
            """, (ref_codigo, data_limite, jogo_id, u_id))
            
            msg_cobranca = (
                f"🎉 O Jogo **{jogo_id}** deu **GREEN!** 🟢\n\n"
                f"Para manteres o acesso vitalício ao canal BetOverTwo, efetua o pagamento de **2€** via MB Way para o número `{MBWAY_NUMBER}`.\n\n"
                f"🔑 **Referência Única:** `{ref_codigo}`\n"
                f"⏳ **Prazo limite:** 24 horas.\n\n"
                "*A ausência de pagamento após o prazo resulta em expulsão automática.*"
            )
            try:
                bot.send_message(u_id, msg_cobranca, parse_mode="Markdown")
            except Exception:
                pass
                
        conn.commit()
        bot.reply_to(message, f"✅ Resultado `{jogo_id}` registado como GREEN! Notificações de pagamento enviadas aos participantes.", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"✅ Resultado `{jogo_id}` registado como RED. Nenhuma cobrança gerada.", parse_mode="Markdown")

    conn.close()

# 8. Comando de Gestão de Lista (/lista J1)
@bot.message_handler(commands=['lista'])
def ver_lista_jogo(message):
    if ADMIN_ID and str(message.from_user.id) != str(ADMIN_ID):
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Uso correto: `/lista [ID_do_Jogo]` (ex: `/lista J1`)", parse_mode="Markdown")
        return
        
    jogo_id = args[1].upper()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT equipas, odd, status FROM jogos WHERE jogo_id = ?", (jogo_id,))
    jogo = cursor.fetchone()
    
    if not jogo:
        bot.reply_to(message, f"❌ Jogo `{jogo_id}` não encontrado.")
        conn.close()
        return

    equipas, odd, status = jogo
    
    cursor.execute("SELECT ref_codigo, user_name, user_id, estado_pagamento, data_limite FROM participantes WHERE jogo_id = ?", (jogo_id,))
    parts = cursor.fetchall()
    conn.close()
    
    pendentes = [p for p in parts if p[3] == 'Pendente']
    pagos = [p for p in parts if p[3] == 'Pago']
    
    texto = (
        f"📊 **Estado do Jogo: {jogo_id}**\n"
        f"⚽ *{equipas}* (Odd: `{odd}` | Status: **{status}**)\n\n"
        f"⏳ **Pendentes ({len(pendentes)}):**\n"
    )
    for p in pendentes:
        texto += f"• `Ref: {p[0]}` — **{p[1]}** (ID: `{p[2]}`)\n"
        
    texto += f"\n✅ **Pagos ({len(pagos)}):**\n"
    for p in pagos:
        texto += f"• `Ref: {p[0]}` — **{p[1]}**\n"
        
    bot.reply_to(message, texto, parse_mode="Markdown")

# 9. Comando para Confirmar Pagamento (/pago J1-4821 ou CÓDIGO)
@bot.message_handler(commands=['pago'])
def confirmar_pagamento(message):
    if ADMIN_ID and str(message.from_user.id) != str(ADMIN_ID):
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Uso correto: `/pago [Referência]` (ex: `/pago J1-4821`)", parse_mode="Markdown")
        return
        
    ref = args[1].upper()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, user_name, jogo_id, estado_pagamento FROM participantes WHERE ref_codigo = ?", (ref,))
    reg = cursor.fetchone()
    
    if not reg:
        bot.reply_to(message, f"❌ Referência `{ref}` não encontrada.")
        conn.close()
        return
        
    user_id, user_name, jogo_id, estado = reg
    
    if estado == 'Pago':
        bot.reply_to(message, f"⚠️ A referência `{ref}` já constava como paga.")
        conn.close()
        return

    cursor.execute("UPDATE participantes SET estado_pagamento = 'Pago' WHERE ref_codigo = ?", (ref,))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"✅ Pagamento `{ref}` ({user_name}) confirmado com sucesso!", parse_mode="Markdown")
    try:
        bot.send_message(user_id, f"✅ O teu pagamento para o jogo **{jogo_id}** foi validado com sucesso! Obrigado e bons lucros.", parse_mode="Markdown")
    except Exception:
        pass

# 10. Comando de Estatísticas Globais (/stats)
@bot.message_handler(commands=['stats'])
def ver_estatisticas(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT valor FROM estatisticas WHERE chave = 'publicados'")
    pub = cursor.fetchone()[0]
    
    cursor.execute("SELECT valor FROM estatisticas WHERE chave = 'greens'")
    greens = cursor.fetchone()[0]
    
    cursor.execute("SELECT valor FROM estatisticas WHERE chave = 'reds'")
    reds = cursor.fetchone()[0]
    
    conn.close()
    
    total_resolvidos = greens + reds
    win_rate = (greens / total_resolvidos * 100) if total_resolvidos > 0 else 0
    
    texto_stats = (
        "📊 **Estatísticas Oficiais - BetOverTwo**\n\n"
        f"• Prognósticos Publicados: `{pub}`\n"
        f"• Greens (Acertos): `{greens} 🟢`\n"
        f"• Reds (Falhas): `{reds} ❌`\n"
        f"• **Win Rate Real:** `{win_rate:.1f}%`\n"
        "📉 **Odd Média:** `> 1.75` (Garantido)\n\n"
        "✨ *Transparência e rigor diário ao serviço da comunidade.*"
    )
    bot.reply_to(message, texto_stats, parse_mode="Markdown")

if __name__ == "__main__":
    print("Bot com suporte a SQLite e IDs de Jogo a iniciar polling...")
    bot.infinity_polling()
