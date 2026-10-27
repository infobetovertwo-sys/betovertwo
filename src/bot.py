import os
import telebot
from dotenv import load_dotenv
from image_generator import Bet2ImageGenerator

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
MBWAY_NUMBER = os.getenv("MBWAY_NUMBER")

bot = telebot.TeleBot(TOKEN)
generator = Bet2ImageGenerator(assets_dir="../assets")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Bem-vindo ao gestor do BetOverTwo! O bot está ativo.")

@bot.message_handler(commands=['publicar'])
def test_publish(message):
    # Dados de teste para o prognóstico
    prog_id = "01"
    data = "27/10"
    hora = "20:45"
    odd = 1.95
    
    try:
        # Gera a imagem do cartão
        image_path = generator.generate_prognostico_card(prog_id, data, hora, odd, is_locked=True)
        
        caption = (
            f"🎯 **PROGNÓSTICO #{prog_id}**\n\n"
            f"⚽ **Mercado:** Ambas Marcam e +2.5 Golos\n"
            f"📊 **Odd:** {odd:.2f}\n"
            f"📅 **Data:** {data} | {hora} WET\n\n"
            f"🔒 **JOGO BLOQUEADO**\n"
            f"🔓 *Desbloqueia este prognóstico por 2€ via MB Way* (`{MBWAY_NUMBER}`).\n"
            f"📩 Envia o comprovativo para ter acesso imediato à análise completa!"
        )
        
        # Envia para o canal configurado
        with open(image_path, 'rb') as photo:
            bot.send_photo(CHANNEL_ID, photo, caption=caption, parse_mode="Markdown")
            
        bot.reply_to(message, "✅ Prognóstico de teste publicado com sucesso no canal!")
    except Exception as e:
        bot.reply_to(message, f"❌ Erro ao publicar: {str(e)}")

if __name__ == "__main__":
    print("Bot BetOverTwo a iniciar...")
    bot.infinity_polling()
