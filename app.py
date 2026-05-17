from flask import Flask, render_template, request, redirect, session, jsonify
import os
import json
import aiohttp
import asyncio
import random
import string
import io
import time
from datetime import timedelta

from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")

# ================= CONFIG =================
USUARIO = "PAPI"
PASSWORD = "DEXTER"
MASTER_KEY = os.environ.get("MASTER_KEY", "CHINITA")

DB_FILE = "database.json"
KEYS_FILE = "keys.json"
STORE_FILE = "store.json"

TOKEN = os.environ.get("BOT_TOKEN")
PUBLIC_URL = os.environ.get("PUBLIC_URL")

ADMIN_ID = 6841201622

API_URL = PUBLIC_URL.rstrip("/") + "/bot/post"

START_TIME = time.time()

# ================= SESSION =================
app.permanent_session_lifetime = timedelta(minutes=5)

# ================= SEGURIDAD =================
@app.before_request
def proteger():

    libres = [
        "/",
        "/bot/post",
        "/logout",
        "/gato",
        "/downloader"
    ]

    if request.path.startswith("/static"):
        return

    if request.path in libres:
        return

    if not session.get("login"):
        return redirect("/")

    session.modified = True

# ================= JSON =================
def load_json(file):

    if not os.path.exists(file):
        return []

    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(file, data):

    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_posts():
    return load_json(DB_FILE)

def save_posts(data):
    save_json(DB_FILE, data)

def load_keys():
    return load_json(KEYS_FILE)

def save_keys(data):
    save_json(KEYS_FILE, data)

def load_store():
    return load_json(STORE_FILE)

def save_store(data):
    save_json(STORE_FILE, data)

def gen_key():

    return ''.join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=16
        )
    )

def get_video_id(url):

    if "v=" in url:
        return url.split("v=")[1].split("&")[0]

    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]

    return None

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        user = request.form.get("user")
        password = request.form.get("pass")
        key = request.form.get("key")

        keys = load_keys()

        if user == USUARIO and password == PASSWORD:

            # MASTER KEY
            if key == MASTER_KEY:

                session.permanent = True
                session["login"] = True

                return redirect("/panel")

            # KEY NORMAL
            if key in keys:

                keys.remove(key)

                save_keys(keys)

                session.permanent = True
                session["login"] = True

                return redirect("/panel")

        return render_template(
            "index.html",
            error="❌ Login incorrecto"
        )

    return render_template("index.html")

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")

# ================= WEB =================
@app.route("/panel")
def panel():
    return render_template("panel.html")

@app.route("/posts")
def posts():

    return render_template(
        "posts.html",
        posts=load_posts()
    )

@app.route("/store")
def store():

    return render_template(
        "store.html",
        productos=load_store()
    )

@app.route("/gato")
def gato():
    return render_template("gato.html")

@app.route("/downloader")
def downloader():
    return render_template("downloader.html")

# ================= BOT POST =================
@app.route("/bot/post", methods=["POST"])
def bot_post():

    data = request.json

    posts = load_posts()

    vid = get_video_id(data.get("youtube"))

    thumb = (
        f"https://img.youtube.com/vi/{vid}/0.jpg"
        if vid else None
    )

    posts.append({
        "youtube": data.get("youtube"),
        "file": data.get("file"),
        "thumbnail": thumb
    })

    save_posts(posts)

    return jsonify({"ok": True})

# ================= BOT =================
def is_admin(update):
    return update.effective_user.id == ADMIN_ID

async def start_cmd(update: Update, ctx):

    if not is_admin(update):
        return

    await update.message.reply_text("""
🤖 BOT ACTIVO

📌 COMANDOS

/yt
/list
/delete
/clear

/addstore
/liststore
/delstore

/stats
/ping
/uptime

/genkey
/delkeysall

/wallhack
""")

# ================= POSTS =================
async def yt(update, ctx):

    if not is_admin(update):
        return

    if len(ctx.args) < 2:

        await update.message.reply_text(
            "Uso: /yt link archivo"
        )

        return

    async with aiohttp.ClientSession() as s:

        await s.post(
            API_URL,
            json={
                "youtube": ctx.args[0],
                "file": ctx.args[1]
            }
        )

    await update.message.reply_text(
        "✅ Publicado"
    )

async def list_cmd(update, ctx):

    if not is_admin(update):
        return

    posts = load_posts()

    txt = "\n".join([
        f"{i} - {p['youtube']}"
        for i, p in enumerate(posts)
    ])

    await update.message.reply_text(
        txt or "Sin posts"
    )

async def delete_cmd(update, ctx):

    if not is_admin(update):
        return

    try:

        i = int(ctx.args[0])

        posts = load_posts()

        posts.pop(i)

        save_posts(posts)

        await update.message.reply_text(
            "Eliminado"
        )

    except:

        await update.message.reply_text(
            "Error"
        )

async def clear(update, ctx):

    if not is_admin(update):
        return

    save_posts([])

    await update.message.reply_text(
        "Todo eliminado"
    )

# ================= STORE =================
async def addstore(update, ctx):

    if not is_admin(update):
        return

    try:

        nombre, precio, desc, link = \
            " ".join(ctx.args).split("|")

        data = load_store()

        data.append({
            "nombre": nombre.strip(),
            "precio": precio.strip(),
            "descripcion": desc.strip(),
            "link": link.strip(),
            "imagen": None
        })

        save_store(data)

        await update.message.reply_text(
            "Producto creado, manda imagen"
        )

    except:

        await update.message.reply_text(
            "Uso: /addstore nombre | precio | desc | link"
        )

async def liststore(update, ctx):

    if not is_admin(update):
        return

    data = load_store()

    if not data:

        await update.message.reply_text(
            "No hay productos"
        )

        return

    txt = "🛒 PRODUCTOS:\n\n"

    for i, p in enumerate(data):
        txt += f"{i} - {p['nombre']} | ${p['precio']}\n"

    await update.message.reply_text(txt)

async def delstore(update, ctx):

    if not is_admin(update):
        return

    try:

        i = int(ctx.args[0])

        data = load_store()

        data.pop(i)

        save_store(data)

        await update.message.reply_text(
            "Producto eliminado"
        )

    except:

        await update.message.reply_text(
            "Uso: /delstore index"
        )

async def foto(update, ctx):

    if not is_admin(update):
        return

    if not update.message.photo:
        return

    file = await update.message.photo[-1].get_file()

    path = f"static/store_{random.randint(1000,9999)}.jpg"

    await file.download_to_drive(path)

    data = load_store()

    if data:

        data[-1]["imagen"] = "/" + path

        save_store(data)

    await update.message.reply_text(
        "Imagen guardada"
    )

# ================= INFO =================
async def stats(update, ctx):

    if not is_admin(update):
        return

    await update.message.reply_text(
        f"Posts: {len(load_posts())}"
    )

async def ping(update, ctx):

    if not is_admin(update):
        return

    await update.message.reply_text("pong")

async def uptime(update, ctx):

    if not is_admin(update):
        return

    t = int(time.time() - START_TIME)

    await update.message.reply_text(
        f"{t}s activo"
    )

# ================= KEYS =================
async def genkey(update, ctx):

    if not is_admin(update):
        return

    n = int(ctx.args[0]) if ctx.args else 1

    keys = load_keys()

    nuevas = [gen_key() for _ in range(n)]

    keys.extend(nuevas)

    save_keys(keys)

    txt = "\n".join(nuevas)

    file = io.BytesIO(txt.encode())
    file.name = "keys.txt"

    await update.message.reply_document(
        InputFile(file)
    )

async def delkeys(update, ctx):

    if not is_admin(update):
        return

    save_keys([])

    await update.message.reply_text(
        "Keys eliminadas"
    )

# ================= WALLHACK =================
async def wallhack(update, ctx):

    if not is_admin(update):
        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "❌ Responde a un AssetBundle"
        )

        return

    msg = update.message.reply_to_message

    if not msg.document:

        await update.message.reply_text(
            "❌ No hay archivo"
        )

        return

    archivo = msg.document

    nombre = archivo.file_name

    await update.message.reply_text(
        f"🧱 Descargando:\n{nombre}"
    )

    try:

        tg_file = await archivo.get_file()

        ruta = f"temp_{nombre}"

        await tg_file.download_to_drive(ruta)

        import UnityPy

        await update.message.reply_text(
            "⚙️ Modificando AssetBundle..."
        )

        env = UnityPy.load(ruta)

        eliminados = 0
        colliders = 0

        for obj in env.objects:

            try:

                if obj.type.name == "GameObject":

                    data = obj.read()

                    # ELIMINAR ICEWALL
                    if hasattr(data, "name"):

                        if "IceWall" in data.name:

                            data.name = "DELETE_ME"

                            obj.save_typetree(data)

                            eliminados += 1

                    # MODIFICAR COLLIDERS
                    tree = obj.read_typetree()

                    txt = str(tree)

                    if "Collider" in txt:

                        nuevo = txt.replace(
                            "true",
                            "false"
                        )

                        if nuevo != txt:
                            colliders += 1

            except:
                pass

        salida = f"mod_{nombre}"

        with open(salida, "wb") as f:
            f.write(env.file.save())

        await update.message.reply_document(
            document=open(salida, "rb"),
            caption=(
                f"✅ WALLHACK LISTO\n\n"
                f"IceWall eliminados: {eliminados}\n"
                f"Colliders modificados: {colliders}"
            )
        )

        try:
            os.remove(ruta)
            os.remove(salida)
        except:
            pass

    except Exception as e:

        await update.message.reply_text(
            f"❌ Error:\n{e}"
        )

# ================= INIT =================
bot = ApplicationBuilder().token(TOKEN).build()

bot.add_handler(CommandHandler("start", start_cmd))

bot.add_handler(CommandHandler("yt", yt))
bot.add_handler(CommandHandler("list", list_cmd))
bot.add_handler(CommandHandler("delete", delete_cmd))
bot.add_handler(CommandHandler("clear", clear))

bot.add_handler(CommandHandler("addstore", addstore))
bot.add_handler(CommandHandler("liststore", liststore))
bot.add_handler(CommandHandler("delstore", delstore))

bot.add_handler(CommandHandler("stats", stats))
bot.add_handler(CommandHandler("ping", ping))
bot.add_handler(CommandHandler("uptime", uptime))

bot.add_handler(CommandHandler("genkey", genkey))
bot.add_handler(CommandHandler("delkeysall", delkeys))

bot.add_handler(CommandHandler("wallhack", wallhack))

bot.add_handler(MessageHandler(filters.PHOTO, foto))

# ================= MAIN =================
async def main():

    await bot.initialize()

    await bot.start()

    print("✅ Bot iniciado")

    await bot.updater.start_polling()

    await asyncio.Event().wait()

if __name__ == "__main__":

    import threading

    threading.Thread(
        target=lambda: asyncio.run(main()),
        daemon=True
    ).start()

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
        )
