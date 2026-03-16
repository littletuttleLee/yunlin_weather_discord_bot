import os
import io
import discord
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from discord.ext import tasks, commands
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import requests

# --- 載入環境變數 ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# 注意：CHANNEL_ID 從 env 抓出來是字串，必須轉成 int
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
SEND_TIME = "08:30"
COMMAND_PREFIX = "!"

# --- 讓機器人保持在線的小網頁 ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    port = 10000
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.daemon = True # 確保主程式結束時 Thread 也跟著結束
    t.start()

# --- 核心爬蟲函數 (保持不變) ---
def get_yunlin_weather_image():
    url = "https://www.cwa.gov.tw/V8/C/S/Ecard/index.html"
    target_alt = "-雲林縣天氣(每日18~19時更新)- 不管天晴天雨，我們都值得擁有好心情！中央氣象署田中氣象站 關心您！"
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # 這裡提醒：在 Linux 伺服器上部署時，通常需要指定 binary_location
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        driver.implicitly_wait(10) 
        img_elements = driver.find_elements(By.CSS_SELECTOR, "#CardList img")
        
        img_url = None
        for img in img_elements:
            alt_text = img.get_attribute("alt")
            if alt_text and target_alt in alt_text:
                img_url = img.get_attribute("src")
                break
        
        if img_url:
            response = requests.get(img_url)
            if response.status_code == 200:
                return io.BytesIO(response.content)
        return None
    except Exception as e:
        print(f"爬取錯誤: {e}")
        return None
    finally:
        driver.quit()

# --- 封裝發送邏輯 ---
async def send_weather_report(channel, type_name):
    today_str = datetime.now().strftime("%Y年%m月%d日")
    async with channel.typing():
        img_data = get_yunlin_weather_image()
        if img_data:
            file = discord.File(img_data, filename="yunlin_weather.jpg")
            await channel.send(content=f"📢 雲林縣天氣小叮嚀 ({type_name})\n📅 日期：{today_str}", file=file)
        else:
            await channel.send(content=f"❌ 抱歉，目前無法取得天氣圖片。")

# --- Discord Bot 類別 ---
class WeatherBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)

    async def setup_hook(self):
        self.daily_task.start()

    async def on_ready(self):
        print(f'✅ 機器人已上線：{self.user}')

    @commands.command(name="weather")
    async def weather(self, ctx):
        print(f"🔹 收到來自 {ctx.author} 的即時請求")
        await send_weather_report(ctx.channel, "即時請求")

    @tasks.loop(minutes=1)
    async def daily_task(self):
        now = datetime.now().strftime("%H:%M")
        if now == SEND_TIME:
            channel = self.get_channel(CHANNEL_ID)
            if channel:
                await send_weather_report(channel, "定時廣播")

# --- 啟動 ---
if __name__ == "__main__":
    keep_alive() # 啟動 Web Server
    bot = WeatherBot()
    bot.run(TOKEN)
