import os
import asyncio
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from telegram import Update, ChatMember
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

# ========= CONFIG =========
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6943566239
DATABASE_URL = os.getenv("DATABASE_URL")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # ej: https://mi-bot.onrender.com
WEBHOOK_PORT = int(os.getenv("PORT", "8443"))

# ========= BASE DE DATOS =========
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # tabla de suscripciones
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            tipo TEXT,
            vence DATE
        )
    """)
    # tabla de miembros
    cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            last_seen TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def add_user(user_id, username, tipo, dias=None):
    conn = get_conn()
    cur = conn.cursor()
    vence = None
    if dias:
        vence = (datetime.now() + timedelta(days=dias)).date()
    cur.execute("""
        INSERT INTO users (user_id, username, tipo, vence)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET username = EXCLUDED.username,
            tipo = EXCLUDED.tipo,
            vence = EXCLUDED.vence
    """, (user_id, username, tipo, vence))
    conn.commit()
    cur.close()
    conn.close()

def remove_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()

def get_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, tipo, vence FROM users WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, tipo, vence FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def update_member(user_id, username, full_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO members (user_id, username, full_name, last_seen)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET username = EXCLUDED.username,
            full_name = EXCLUDED.full_name,
            last_seen = NOW()
    """, (user_id, username, full_name))
    conn.commit()
    cur.close()
    conn.close()

def get_member_by_username(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, full_name FROM members WHERE username=%s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def get_member_by_id(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, full_name FROM members WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

# ========= HELPERS =========
def username_or_id(username, user_id):
    return f"@{username}" if username else str(user_id)

async def resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """resolver usuario desde reply, @usuario o ID (usando tabla members)."""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user

    if not context.args:
        return None

    arg = context.args[0]
    if arg.isdigit():  # ID numérico
        member = get_member_by_id(int(arg))
        if member:
            class Temp: pass
            u = Temp()
            u.id, u.username, u.full_name = member
            return u
        else:
            return None
    else:  # @usuario
        username_arg = arg.lstrip("@")
        member = get_member_by_username(username_arg)
        if member:
            class Temp: pass
            u = Temp()
            u.id, u.username, u.full_name = member
            return u
        else:
            return None

# ========= HANDLERS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        await update.message.reply_text(
            "𓈒 ࣪ ˖ ¡holi! soy el bot encargado de llevar tu suscripción dentro de 𝔀inter 𝓹riv. "
            "usa el comando /mysub para ver su estado. ♪ 🪽🪽"
        )

async def sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2 and not update.message.reply_to_message:
        await update.message.reply_text("uso: /sub @usuario {días}")
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("no se pudo encontrar al usuario.")
        return

    try:
        dias = int(context.args[1]) if len(context.args) > 1 else 30
    except ValueError:
        await update.message.reply_text("los días deben ser un número.")
        return

    add_user(user.id, user.username or user.full_name, "premium", dias)
    fecha_vencimiento = (datetime.now() + timedelta(days=dias)).strftime("%d/%m/%Y")
    await update.message.reply_text(
        f"¡hola, {user.full_name}! se han añadido {dias} días a tu suscripción premium.\n"
        f"🪽⊹ tu cupo vence el {fecha_vencimiento}"
    )

async def free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("uso: /free @usuario")
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("no se pudo encontrar al usuario.")
        return

    add_user(user.id, user.username or user.full_name, "free")
    await update.message.reply_text(
        f"¡hola, {user.full_name}! eres cupo free dentro de 𝔀inter 𝓹riv. "
        "recuerda mandar un mínimo 4 referencias semanales para continuar con tu cupo. ❤︎"
    )

async def addmod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("uso: /addmod @usuario (o responde a su mensaje).")
        return

    add_user(user.id, user.username or user.full_name, "mod")
    await update.message.reply_text(
        f"¡hola, {user.full_name}! ahora eres parte del staff "
        "con cupo ilimitado dentro de 𝔀inter 𝓹riv. 🪽⊹"
    )

async def unmod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("uso: /unmod @usuario (o responde a su mensaje).")
        return

    remove_user(user.id)
    await update.message.reply_text(
        f"{user.full_name} ha sido removido del staff de 𝔀inter 𝓹riv."
    )

async def unsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("uso: /unsub @usuario (o responde a su mensaje).")
        return

    try:
        remove_user(user.id)
        # kick temporal
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"{user.full_name} fue expulsado de 𝔀inter 𝓹riv..")
    except Exception as e:
        await update.message.reply_text(f"error al expulsar: {e}")

async def mysub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # 👑 Si es el owner
    if user.id == ADMIN_ID:
        await update.message.reply_text("blud eres el owner.")
        return

    sub = get_user(user.id)
    if not sub:
        await update.message.reply_text("no tienes ninguna suscripción activa.")
        return

    username, tipo, vence = sub
    nombre = user.full_name

    if tipo == "premium":
        await update.message.reply_text(
            f"¡hola, {nombre}! eres cupo premium dentro de 𝔀inter 𝓹riv.\n"
            f"🪽⊹ tu cupo vence el {vence.strftime('%d/%m/%Y') if vence else 'desconocido'}"
        )
    elif tipo == "free":
        await update.message.reply_text(
            f"¡hola, {nombre}! eres cupo free dentro de 𝔀inter 𝓹riv. "
        "recuerda mandar un mínimo 4 referencias semanales para continuar con tu cupo. ❤︎"
        )
    elif tipo == "mod":
        await update.message.reply_text(
            f"¡hola, {nombre}! eres parte del staff en 𝔀inter 𝓹riv. "
            "tu cupo es ilimitado mientras seas parte de nuestra administración. 🪽⊹"
        )

async def listmods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    usuarios = get_all_users()
    mods = [f"- {username_or_id(username, user_id)}" for user_id, username, tipo, vence in usuarios if tipo == "mod"]

    if not mods:
        await update.message.reply_text("no hay miembros del staff registrados.")
    else:
        await update.message.reply_text("𝓐dministración\n" + "\n".join(mods))

async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    usuarios = get_all_users()
    if not usuarios:
        await update.message.reply_text("no hay usuarios registrados en la base de datos.")
        return

    texto = "𝓜iembros\n"
    for user_id, username, tipo, vence in usuarios:
        nombre = username_or_id(username, user_id)

        if tipo == "premium":
            texto += f"- {nombre} | premium (vence: {vence.strftime('%d/%m/%Y') if vence else '??'})\n"
        elif tipo == "free":
            texto += f"- {nombre} | free\n"
        elif tipo == "mod":
            texto += f"- {nombre} | staff (mod)\n"

    await update.message.reply_text(texto)

async def whois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("uso: /whois @usuario (o responde a su mensaje).")
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("usuario no encontrado en la base de datos.")
        return

    sub = get_user(user.id)
    if not sub:
        await update.message.reply_text(f"{username_or_id(user.username, user.id)} no tiene suscripción activa.")
        return

    username, tipo, vence = sub
    nombre = username_or_id(username, user.id)

    if tipo == "premium":
        await update.message.reply_text(
            f"{nombre} tiene suscripción premium hasta el {vence.strftime('%d/%m/%Y') if vence else 'desconocido'}."
        )
    elif tipo == "free":
        await update.message.reply_text(f"{nombre} tiene cupo free.")
    elif tipo == "mod":
        await update.message.reply_text(f"{nombre} es admin del priv.")

# ========= TRACKING =========
async def track_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        update_member(user.id, user.username, user.full_name)

async def track_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_member: ChatMember = update.chat_member
    user = chat_member.from_user
    if user:
        update_member(user.id, user.username, user.full_name)

# ========= RECORDATORIOS =========
async def reminder_job(context):
    usuarios = get_all_users()
    for user_id, username, tipo, vence in usuarios:
        if tipo == "premium" and vence:
            fecha_venc = vence
            if fecha_venc - timedelta(days=2) == datetime.now().date():
                try:
                    await context.bot.send_message(
                        user_id,
                        f"¡holi! tu suscripción vence el {fecha_venc.strftime('%d/%m/%Y')} "
                        "puedes contactar al owner para renovar."
                    )
                except:
                    pass

# ========= MAIN =========
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sub", sub))
    app.add_handler(CommandHandler("free", free))
    app.add_handler(CommandHandler("addmod", addmod))
    app.add_handler(CommandHandler("unmod", unmod))
    app.add_handler(CommandHandler("unsub", unsub))
    app.add_handler(CommandHandler("mysub", mysub))
    app.add_handler(CommandHandler("listmods", listmods))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("whois", whois))

    # tracking de usuarios
    app.add_handler(MessageHandler(filters.ALL, track_messages))
    app.add_handler(ChatMemberHandler(track_chat_members, ChatMemberHandler.CHAT_MEMBER))

    # recordatorio 1 vez al día
    app.job_queue.run_repeating(reminder_job, interval=86400, first=10)

    print("bot corriendo con WEBHOOK...")
    app.run_webhook(
        listen="0.0.0.0",
        port=WEBHOOK_PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
