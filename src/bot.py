import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot

# 1. Servidor web falso para manter o Render feliz (evita o timeout de portas)
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"Starting fake web server on port {port}...")
    server.serve_forever()

# Inicia o servidor web numa thread separada em segundo plano
web_thread = threading.Thread(target=run_web_server, daemon=True)
web_thread.start()

# 2. Configuração do Bot do Telegram
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
MBWAY_NUMBER = os.environ.get("MBWAY_NUMBER")

if not TOKEN:
    raise ValueError("A variável de ambiente TELEGRAM_BOT_TOKEN não está definida.")

bot = telebot.TeleBot(TOKEN)

# Exemplo de comando básico para testar
@bot.message_handler(commands=['start', 'publicar'])
def send_welcome(message):
    bot.reply_to(message, "🤖 O bot do BetOverTwo está online e operacional!")

if __name__ == "__main__":
    print("Bot a iniciar o polling...")
    bot.infinity_polling()
