from flask import Flask, render_template, request, redirect, session, jsonify
import os
import json
import aiohttp
import asyncio
import random
import string
import io
import time
import re
import hashlib

from datetime import timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram import InputFile  # 🔥 IMPORTANTE: InputFile va aquí

import UnityPy

# ==================== FLASK APP ====================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key_chinita_2026")
app.permanent_session_lifetime = timedelta(minutes=30)

# ==================== CONFIGURACIÓN ====================
USUARIO = "PAPI"
PASSWORD = "DEXTER"

MASTER_KEY = os.environ.get("MASTER_KEY", "CHINITA")

DB_FILE = "database.json"
KEYS_FILE = "keys.json"
STORE_FILE = "store.json"

TOKEN = os.environ.get("BOT_TOKEN")
PUBLIC_URL = os.environ.get("PUBLIC_URL")

ADMIN_ID = 6841201622

API_URL = PUBLIC_URL.rstrip("/") + "/bot/post" if PUBLIC_URL else "http://localhost:10000/bot/post"

START_TIME = time.time()

TEMP_DIR = "temp"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

if not os.path.exists("static"):
    os.makedirs("static")

# ==================== FUNCIONES JSON ====================
def load_json(file):
    if not os.path.exists(file):
        return []
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_posts(): return load_json(DB_FILE)
def save_posts(d): save_json(DB_FILE, d)
def load_keys(): return load_json(KEYS_FILE)
def save_keys(d): save_json(KEYS_FILE, d)
def load_store(): return load_json(STORE_FILE)
def save_store(d): save_json(STORE_FILE, d)

def gen_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def get_video_id(url):
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return None

# ==================== SEGURIDAD WEB ====================
@app.before_request
def proteger():
    libres = ["/", "/bot/post", "/webhook", "/logout", "/gato", "/downloader"]
    if request.path.startswith("/static"):
        return
    if request.path in libres:
        return
    if not session.get("login"):
        return redirect("/")
    session.modified = True

# ==================== RUTAS WEB ====================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user")
        password = request.form.get("pass")
        key = request.form.get("key")
        keys = load_keys()
        
        if user == USUARIO and password == PASSWORD:
            if key == MASTER_KEY or key in keys:
                if key in keys and key != MASTER_KEY:
                    keys.remove(key)
                    save_keys(keys)
                session.permanent = True
                session["login"] = True
                return redirect("/panel")
        return render_template("index.html", error="❌ Login incorrecto")
    return render_template("index.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/panel")
def panel():
    return render_template("panel.html")

@app.route("/posts")
def posts():
    return render_template("posts.html", posts=load_posts())

@app.route("/store")
def store():
    return render_template("store.html", productos=load_store())

@app.route("/gato")
def gato():
    return render_template("gato.html")

@app.route("/downloader")
def downloader():
    return render_template("downloader.html")

@app.route("/bot/post", methods=["POST"])
def bot_post():
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400
    
    posts = load_posts()
    vid = get_video_id(data.get("youtube"))
    thumb = f"https://img.youtube.com/vi/{vid}/0.jpg" if vid else None
    
    posts.append({
        "youtube": data.get("youtube"),
        "file": data.get("file"),
        "thumbnail": thumb,
        "created": time.time()
    })
    save_posts(posts)
    return jsonify({"ok": True})

# ==================== BOT ====================
def is_admin(update):
    return update.effective_user.id == ADMIN_ID

# ==================== MENÚ PRINCIPAL ====================
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ No autorizado")
        return
    
    keyboard = [
        [InlineKeyboardButton("📹 YouTube", callback_data="menu_yt")],
        [InlineKeyboardButton("🛒 Tienda", callback_data="menu_store")],
        [InlineKeyboardButton("🔑 Keys", callback_data="menu_keys")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="menu_info")]
    ]
    
    await update.message.reply_text(
        "🤖 **PAPI DEXTER BOT**\n\nSelecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== MENÚ YOUTUBE ====================
async def menu_yt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📥 Agregar Video", callback_data="yt_add")],
        [InlineKeyboardButton("📋 Listar Videos", callback_data="yt_list")],
        [InlineKeyboardButton("🗑️ Eliminar Video", callback_data="yt_delete")],
        [InlineKeyboardButton("🧹 Limpiar Todo", callback_data="yt_clear")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "📹 **GESTIÓN DE VIDEOS**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def yt_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📥 **Agregar Video**\n\n"
        "Formato:\n"
        "`/yt link_youtube nombre_archivo`\n\n"
        "Ejemplo:\n"
        "`/yt https://youtu.be/xxxxx video1`\n\n"
        "📌 El archivo se guardará como: `video1.unity3d`",
        parse_mode="Markdown"
    )

async def yt_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    posts = load_posts()
    if not posts:
        await query.edit_message_text("📋 No hay videos guardados.")
        return
    
    txt = "📋 **VIDEOS GUARDADOS:**\n\n"
    for i, p in enumerate(posts):
        nombre = p.get('file', 'sin nombre')
        link = p.get('youtube', 'sin link')
        txt += f"{i}. {nombre}\n   {link[:50]}...\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_yt")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def yt_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    posts = load_posts()
    if not posts:
        await query.edit_message_text("📋 No hay videos para eliminar.")
        return
    
    keyboard = []
    for i, p in enumerate(posts):
        nombre = p.get('file', f'video_{i}')
        keyboard.append([InlineKeyboardButton(f"🗑️ {i} - {nombre[:20]}", callback_data=f"del_yt_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_yt")])
    
    await query.edit_message_text(
        "🗑️ **SELECCIONA VIDEO A ELIMINAR:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def yt_delete_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        idx = int(query.data.split("_")[2])
        posts = load_posts()
        
        if 0 <= idx < len(posts):
            removed = posts.pop(idx)
            save_posts(posts)
            await query.edit_message_text(f"✅ Video eliminado: {removed.get('file', 'sin nombre')}")
        else:
            await query.edit_message_text("❌ Error: Video no encontrado")
    except:
        await query.edit_message_text("❌ Error al eliminar")
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_yt")]]
    await query.edit_message_text(
        "🗑️ **ELIMINADO**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def yt_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ SI, limpiar todo", callback_data="yt_clear_confirm")],
        [InlineKeyboardButton("❌ NO, cancelar", callback_data="menu_yt")]
    ]
    
    await query.edit_message_text(
        "⚠️ **¿ELIMINAR TODOS LOS VIDEOS?**\n\nEsta acción no se puede deshacer.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def yt_clear_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    save_posts([])
    await query.edit_message_text("🧹 Todos los videos eliminados.")

# ==================== MENÚ TIENDA ====================
async def menu_store(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Agregar Producto", callback_data="store_add")],
        [InlineKeyboardButton("📋 Listar Productos", callback_data="store_list")],
        [InlineKeyboardButton("🗑️ Eliminar Producto", callback_data="store_delete")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🛒 **GESTIÓN DE TIENDA**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def store_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📦 **Agregar Producto**\n\n"
        "Formato:\n"
        "`/addstore nombre | precio | descripción | link`\n\n"
        "Ejemplo:\n"
        "`/addstore Skin XP | 10.99 | Skin exclusiva | https://link.com`\n\n"
        "📌 Después de agregar, envía una imagen del producto.",
        parse_mode="Markdown"
    )

async def store_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_store()
    if not data:
        await query.edit_message_text("🛒 No hay productos en la tienda.")
        return
    
    txt = "🛒 **PRODUCTOS:**\n\n"
    for i, p in enumerate(data):
        txt += f"{i} - {p.get('nombre', 'sin nombre')} | ${p.get('precio', '0')}\n"
        if p.get('imagen'):
            txt += f"   🖼️ [Ver imagen]({p['imagen']})\n"
        txt += "\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_store")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def store_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_store()
    if not data:
        await query.edit_message_text("🛒 No hay productos para eliminar.")
        return
    
    keyboard = []
    for i, p in enumerate(data):
        nombre = p.get('nombre', f'producto_{i}')
        keyboard.append([InlineKeyboardButton(f"🗑️ {i} - {nombre[:20]}", callback_data=f"del_store_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_store")])
    
    await query.edit_message_text(
        "🗑️ **SELECCIONA PRODUCTO A ELIMINAR:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def store_delete_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        idx = int(query.data.split("_")[2])
        data = load_store()
        
        if 0 <= idx < len(data):
            removed = data.pop(idx)
            save_store(data)
            await query.edit_message_text(f"✅ Producto eliminado: {removed.get('nombre', 'sin nombre')}")
        else:
            await query.edit_message_text("❌ Error: Producto no encontrado")
    except:
        await query.edit_message_text("❌ Error al eliminar")
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_store")]]
    await query.edit_message_text(
        "🗑️ **ELIMINADO**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== MENÚ KEYS ====================
async def menu_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔑 Generar Keys", callback_data="keys_gen")],
        [InlineKeyboardButton("📋 Ver Keys", callback_data="keys_list")],
        [InlineKeyboardButton("🗑️ Eliminar Keys", callback_data="keys_del")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🔑 **GESTIÓN DE KEYS**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def keys_gen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔑 **Generar Keys**\n\n"
        "Formato:\n"
        "`/genkey cantidad`\n\n"
        "Ejemplo:\n"
        "`/genkey 5`\n\n"
        "📌 Las keys se enviarán en un archivo .txt",
        parse_mode="Markdown"
    )

async def keys_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keys = load_keys()
    if not keys:
        await query.edit_message_text("🔑 No hay keys generadas.")
        return
    
    txt = "🔑 **KEYS GENERADAS:**\n\n"
    for i, k in enumerate(keys):
        txt += f"{i+1}. `{k}`\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_keys")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def keys_del(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ SI, eliminar todas", callback_data="keys_del_confirm")],
        [InlineKeyboardButton("❌ NO, cancelar", callback_data="menu_keys")]
    ]
    
    await query.edit_message_text(
        "⚠️ **¿ELIMINAR TODAS LAS KEYS?**\n\nEsta acción no se puede deshacer.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def keys_del_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    save_keys([])
    await query.edit_message_text("🗑️ Todas las keys eliminadas.")

# ==================== MENÚ ESTADÍSTICAS ====================
async def menu_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    posts = len(load_posts())
    store = len(load_store())
    keys = len(load_keys())
    uptime_sec = int(time.time() - START_TIME)
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60
    seconds = uptime_sec % 60
    
    txt = f"""📊 **ESTADÍSTICAS**

📹 Videos: {posts}
🛒 Productos: {store}
🔑 Keys: {keys}
⏱️ Uptime: {hours}h {minutes}m {seconds}s

🤖 Bot activo ✅"""
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== MENÚ INFO ====================
async def menu_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    txt = """ℹ️ **PAPI DEXTER BOT**

🤖 Bot de gestión para Unity Assets

📌 **Funciones:**
• Gestión de videos YouTube
• Tienda de productos
• Generación de keys
• Estadísticas en tiempo real

👤 Admin: PAPI DEXTER
🔐 Seguro y rápido

⚡ Versión 2.0 - Botones interactivos"""
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== BACK TO MAIN ====================
async def back_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📹 YouTube", callback_data="menu_yt")],
        [InlineKeyboardButton("🛒 Tienda", callback_data="menu_store")],
        [InlineKeyboardButton("🔑 Keys", callback_data="menu_keys")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="menu_info")]
    ]
    
    await query.edit_message_text(
        "🤖 **PAPI DEXTER BOT**\n\nSelecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== COMANDOS DE TEXTO (COMPATIBILIDAD) ====================
async def yt_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if len(ctx.args) < 2:
        await update.message.reply_text("Uso: /yt link archivo")
        return
    
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(API_URL, json={"youtube": ctx.args[0], "file": ctx.args[1]})
        await update.message.reply_text(f"✅ Video publicado: {ctx.args[1]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def addstore_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        texto = " ".join(ctx.args)
        partes = texto.split("|")
        if len(partes) < 4:
            await update.message.reply_text("Uso: /addstore nombre | precio | desc | link")
            return
        
        nombre, precio, desc, link = partes[0].strip(), partes[1].strip(), partes[2].strip(), partes[3].strip()
        data = load_store()
        data.append({
            "nombre": nombre,
            "precio": precio,
            "descripcion": desc,
            "link": link,
            "imagen": None
        })
        save_store(data)
        await update.message.reply_text(f"✅ Producto creado: {nombre}\n📸 Envía una imagen para el producto.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def genkey_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        n = int(ctx.args[0]) if ctx.args else 1
        if n > 100:
            await update.message.reply_text("❌ Máximo 100 keys por vez")
            return
        
        keys = load_keys()
        nuevas = [gen_key() for _ in range(n)]
        keys.extend(nuevas)
        save_keys(keys)
        
        txt = "\n".join(nuevas)
        file = io.BytesIO(txt.encode())
        file.name = "keys.txt"
        
        await update.message.reply_document(InputFile(file, filename="keys.txt"))
    except ValueError:
        await update.message.reply_text
