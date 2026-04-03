from flask import Flask, render_template, request, redirect, session, jsonify
import os, json, aiohttp, asyncio, random, string, io, time, threading
from datetime import timedelta, datetime
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")
app.permanent_session_lifetime = timedelta(minutes=5)

# ================= CONFIG =================
USUARIO = "PAPI"
PASSWORD = "DEXTER"
MASTER_KEY = os.environ.get("MASTER_KEY", "CHINITA")

DB_FILE = "database.json"
KEYS_FILE = "keys.json"
STORE_FILE = "store.json"

TOKEN = os.environ.get("BOT_TOKEN")
PUBLIC_URL = os.environ.get("PUBLIC_URL")

ADMIN_ID = 2122510061
START_TIME = time.time()

# Variables para controlar el sleep del bot
bot_activo = True
ultima_actividad = time.time()
TIMEOUT_INACTIVIDAD = 300  # 5 minutos

# ================= SEGURIDAD =================
@app.before_request
def proteger():
    libres = ["/", "/bot/post", "/webhook", "/logout", "/gato", "/downloader", "/memoria", "/health", "/wake_bot"]
    if request.path.startswith("/static"):
        return
    if request.path in libres:
        return
    if not session.get("login"):
        return redirect("/")
    session.modified = True

# ================= JSON CON CACHE =================
_cache_timestamp = {}
_cache_data = {}

def load_json_cached(file, max_age=10):
    now = time.time()
    if file in _cache_timestamp and (now - _cache_timestamp[file]) < max_age:
        return _cache_data[file]
    if not os.path.exists(file):
        data = []
    else:
        with open(file, 'r') as f:
            data = json.load(f)
    _cache_timestamp[file] = now
    _cache_data[file] = data
    return data

def save_json_clear_cache(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)
    if file in _cache_timestamp:
        del _cache_timestamp[file]
        del _cache_data[file]

def load_posts(): return load_json_cached(DB_FILE)
def save_posts(d): save_json_clear_cache(DB_FILE, d)
def load_keys(): return load_json_cached(KEYS_FILE)
def save_keys(d): save_json_clear_cache(KEYS_FILE, d)
def load_store(): return load_json_cached(STORE_FILE)
def save_store(d): save_json_clear_cache(STORE_FILE, d)

def gen_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

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
            if key == MASTER_KEY or key in keys:
                if key != MASTER_KEY and key in keys:
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

# ================= WEB =================
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

@app.route("/memoria")
def memoria_status():
    try:
        import psutil
        proceso = psutil.Process()
        memoria_mb = proceso.memory_info().rss / 1024 / 1024
        estado_bot = "🟢 ACTIVO" if bot_activo else "🔴 DORMIDO"
        return f"""
        <h1>📊 Estado</h1>
        <p>Memoria: {memoria_mb:.2f} MB</p>
        <p>Bot: {estado_bot}</p>
        <p>Ultima actividad: {datetime.fromtimestamp(ultima_actividad).strftime('%H:%M:%S')}</p>
        <a href='/panel'>Volver</a>
        """
    except:
        return "Instala psutil"

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "uptime": int(time.time() - START_TIME),
        "bot_activo": bot_activo
    })

@app.route("/wake_bot")
def wake_bot():
    """Endpoint para despertar el bot manualmente"""
    global bot_activo, ultima_actividad
    bot_activo = True
    ultima_actividad = time.time()
    return jsonify({"status": "Bot despertado"})

# ================= BOT POST =================
@app.route("/bot/post", methods=["POST"])
def bot_post():
    data = request.json
    posts = load_posts()
    vid = get_video_id(data.get("youtube"))
    thumb = f"https://img.youtube.com/vi/{vid}/0.jpg" if vid else None
    posts.append({
        "youtube": data.get("youtube"),
        "file": data.get("file"),
        "thumbnail": thumb
    })
    save_posts(posts)
    return jsonify({"ok": True})

# ================= HANDLERS DEL BOT =================
def is_admin(update):
    return update.effective_user.id == ADMIN_ID

async def start_cmd(update, ctx):
    if not is_admin(update): return
    await update.message.reply_text("""
🤖 BOT ACTIVO

📌 COMANDOS:
/yt /list /delete /clear
/addstore /liststore /delstore
/stats /ping /uptime
/genkey /delkeysall
""")

async def yt(update, ctx):
    if not is_admin(update) or len(ctx.args) < 2:
        return
    async with aiohttp.ClientSession() as s:
        await s.post(PUBLIC_URL + "/bot/post", json={
            "youtube": ctx.args[0],
            "file": ctx.args[1]
        })
    await update.message.reply_text("✅ Publicado")

async def list_cmd(update, ctx):
    if not is_admin(update): return
    posts = load_posts()
    txt = "\n".join([f"{i} - {p['youtube']}" for i,p in enumerate(posts)]) or "Sin posts"
    await update.message.reply_text(txt)

async def delete_cmd(update, ctx):
    if not is_admin(update): return
    try:
        posts = load_posts()
        posts.pop(int(ctx.args[0]))
        save_posts(posts)
        await update.message.reply_text("Eliminado")
    except:
        await update.message.reply_text("Error")

async def clear(update, ctx):
    if not is_admin(update): return
    save_posts([])
    await update.message.reply_text("Todo eliminado")

async def addstore(update, ctx):
    if not is_admin(update): return
    try:
        nombre, precio, desc, link = " ".join(ctx.args).split("|")
        data = load_store()
        data.append({
            "nombre": nombre.strip(),
            "precio": precio.strip(),
            "descripcion": desc.strip(),
            "link": link.strip(),
            "imagen": None
        })
        save_store(data)
        await update.message.reply_text("Producto creado, manda imagen")
    except:
        await update.message.reply_text("Uso: /addstore nombre | precio | desc | link")

async def liststore(update, ctx):
    if not is_admin(update): return
    data = load_store()
    if not data:
        await update.message.reply_text("No hay productos")
        return
    txt = "🛒 PRODUCTOS:\n\n" + "\n".join([f"{i} - {p['nombre']} | ${p['precio']}" for i, p in enumerate(data)])
    await update.message.reply_text(txt)

async def delstore(update, ctx):
    if not is_admin(update): return
    try:
        data = load_store()
        data.pop(int(ctx.args[0]))
        save_store(data)
        await update.message.reply_text("Producto eliminado")
    except:
        await update.message.reply_text("Uso: /delstore index")

async def foto(update, ctx):
    if not is_admin(update) or not update.message.photo:
        return
    file = await update.message.photo[-1].get_file()
    path = f"static/store_{random.randint(1000,9999)}.jpg"
    await file.download_to_drive(path)
    data = load_store()
    if data:
        data[-1]["imagen"] = "/" + path
        save_store(data)
    await update.message.reply_text("Imagen guardada")

async def stats(update, ctx):
    if not is_admin(update): return
    await update.message.reply_text(f"Posts: {len(load_posts())}")

async def ping(update, ctx):
    if not is_admin(update): return
    await update.message.reply_text("pong")

async def uptime(update, ctx):
    if not is_admin(update): return
    await update.message.reply_text(f"{int(time.time() - START_TIME)}s activo")

async def genkey(update, ctx):
    if not is_admin(update): return
    n = int(ctx.args[0]) if ctx.args else 1
    keys = load_keys()
    nuevas = [gen_key() for _ in range(n)]
    keys.extend(nuevas)
    save_keys(keys)
    file = io.BytesIO("\n".join(nuevas).encode())
    file.name = "keys.txt"
    await update.message.reply_document(InputFile(file))

async def delkeys(update, ctx):
    if not is_admin(update): return
    save_keys([])
    await update.message.reply_text("Keys eliminadas")

# ================= BOT CON SLEEP MODE =================
print("🤖 Iniciando bot con SLEEP MODE...")
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
bot.add_handler(MessageHandler(filters.PHOTO, foto))

# Controlador de sleep
def bot_sleep_manager():
    global bot_activo, ultima_actividad
    while True:
        time.sleep(60)  # Revisar cada minuto
        ahora = time.time()
        if bot_activo and (ahora - ultima_actividad) > TIMEOUT_INACTIVIDAD:
            bot_activo = False
            print(f"💤 Bot dormido por inactividad de {TIMEOUT_INACTIVIDAD//60} minutos - RAM liberada")
            # Forzar garbage collection
            import gc
            gc.collect()

# Actualizar actividad cuando el bot recibe algo
async def update_activity(update, context):
    global bot_activo, ultima_actividad
    if not bot_activo:
        bot_activo = True
        print("🔵 Bot despertado por mensaje")
    ultima_actividad = time.time()

# Middleware para actualizar actividad en cada mensaje
bot.add_handler(MessageHandler(filters.ALL, update_activity), group=1)

# Iniciar el bot en modo polling
def run_bot():
    print("✅ Bot iniciado. Esperando comandos...")
    bot.run_polling()

bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# Iniciar el manager de sleep
sleep_manager_thread = threading.Thread(target=bot_sleep_manager, daemon=True)
sleep_manager_thread.start()

# ================= WEBHOOK SIMPLE (opcional) =================
@app.route("/webhook", methods=["POST"])
def webhook():
    global ultima_actividad, bot_activo
    ultima_actividad = time.time()
    if not bot_activo:
        bot_activo = True
        print("🔵 Bot despertado por webhook")
    try:
        update = Update.de_json(request.get_json(force=True), bot.bot)
        # Procesar en un hilo separado
        threading.Thread(target=lambda: asyncio.run(bot.process_update(update))).start()
        return "ok", 200
    except Exception as e:
        print(f"Error: {e}")
        return "error", 500

# ================= EJECUCIÓN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Web iniciada en puerto {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
