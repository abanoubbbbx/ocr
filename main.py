import os
import io
import json
import discord
import asyncio
import requests
import aiohttp
import tempfile
import shutil
from discord.ext import commands
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from paddleocr import PaddleOCR

# إعداد Discord Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# إعداد Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

# دالة لجلب الصور من Google Drive
def get_image_files(service, folder_id):
    results = service.files().list(
        q=f"'{folder_id}' in parents and mimeType contains 'image/'",
        fields="files(id, name)").execute()
    return results.get('files', [])

# دالة لتحميل صورة مؤقتاً
def download_image(service, file_id):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = googleapiclient.http.MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh

# تحليل الصورة باستخدام PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='japan+chinese+korean')  # no paddlex

def run_ocr(image_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
        temp.write(image_bytes.read())
        temp.flush()
        result = ocr.ocr(temp.name, cls=True)
        os.unlink(temp.name)

    texts = []
    for line in result:
        for box in line:
            text = box[1][0].strip()
            if text:
                texts.append(text)
    return texts

# أمر Discord
@bot.command()
async def ocr(ctx, folder_link: str):
    await ctx.send("🔍 جاري جلب الصور من Google Drive...")
    try:
        folder_id = None
        if "folders/" in folder_link:
            folder_id = folder_link.split("folders/")[1].split("?")[0]
        elif "id=" in folder_link:
            folder_id = folder_link.split("id=")[1].split("&")[0]

        if not folder_id:
            return await ctx.send("❌ لم يتم العثور على معرف الفولدر")

        service = get_drive_service()
        files = get_image_files(service, folder_id)
        if not files:
            return await ctx.send("❌ لا توجد صور داخل الفولدر")

        all_text = ""
        for idx, file in enumerate(files):
            img = download_image(service, file['id'])
            texts = run_ocr(img)
            all_text += f"\n\n📄 الصفحة {idx+1}:\n" + "\n".join(texts)

        if len(all_text) > 1900:
            with open("output.txt", "w", encoding="utf-8") as f:
                f.write(all_text)
            await ctx.send("📄 تم الاستخراج:", file=discord.File("output.txt"))
            os.remove("output.txt")
        else:
            await ctx.send(f"📄 تم الاستخراج:\n{all_text}")

    except Exception as e:
        print("OCR Error:", e)
        await ctx.send("❌ حدث خطأ أثناء تحليل الصور")

# شغّل البوت
bot.run("توكن_البوت_بتاعك")
