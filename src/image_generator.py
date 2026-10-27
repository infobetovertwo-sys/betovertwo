import os
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

COLOR_BG = "#2C2C2C"      # Cinzento escuro
COLOR_GREEN = "#00FFC2"   # Verde menta
COLOR_WHITE = "#FFFFFF"   # Branco

class Bet2ImageGenerator:
    def __init__(self, assets_dir="../assets"):
        self.assets_dir = assets_dir
        # Procura por logo.jpeg (ou logo.png como alternativa)
        self.logo_path = os.path.join(assets_dir, "logo.jpeg")
        if not os.path.exists(self.logo_path):
            self.logo_path = os.path.join(assets_dir, "logo.png")
            
        self.font_path = os.path.join(assets_dir, "font.ttf")
        
        if os.path.exists(self.logo_path):
            self.logo = Image.open(self.logo_path).convert("RGBA")
        else:
            self.logo = None
            
        if os.path.exists(self.font_path):
            self.font_id = ImageFont.truetype(self.font_path, 40)
            self.font_market = ImageFont.truetype(self.font_path, 32)
            self.font_data = ImageFont.truetype(self.font_path, 28)
        else:
            self.font_id = ImageFont.load_default()
            self.font_market = ImageFont.load_default()
            self.font_data = ImageFont.load_default()

    def generate_prognostico_card(self, prog_id, date, time, odd, is_locked=True):
        width, height = 800, 500
        img = Image.new('RGBA', (width, height), color=COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        margin = 20
        draw.line([(margin, 100), (width-margin, 100)], fill=COLOR_GREEN, width=2)
        
        if self.logo:
            logo_w = 120
            logo_h = int(logo_w * (self.logo.height / self.logo.width))
            logo_res = self.logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
            img.paste(logo_res, (margin + 10, 15), logo_res)
        
        id_text = f"PROG #{prog_id}"
        draw.text((width - margin - 200, 30), id_text, fill=COLOR_WHITE, font=self.font_id)
        
        draw.text((margin + 20, 130), "MERCADO:", fill=COLOR_GREEN, font=self.font_market)
        draw.text((margin + 20, 175), "Ambas Marcam e +2.5 Golos", fill=COLOR_WHITE, font=self.font_market)
        
        draw.text((margin + 20, 260), "ODD BETANO:", fill=COLOR_GREEN, font=self.font_data)
        draw.text((margin + 20, 300), f"{odd:.2f}", fill=COLOR_WHITE, font=self.font_id)
        
        date_text = f"DATA: {date} | {time} WET"
        draw.text((width - margin - 350, 280), date_text, fill=COLOR_WHITE, font=self.font_data)

        if is_locked:
            lock_text = "JOGO BLOQUEADO"
            draw.text(((width - 200) // 2, height - margin - 50), lock_text, fill=COLOR_WHITE, font=self.font_market)
            
        temp_path = "temp_card.png"
        img.save(temp_path)
        return temp_path
