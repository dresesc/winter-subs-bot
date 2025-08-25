import os 
import asyncio
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from telegram import Update, ChatAdministratorRights, ChatMemberAdministrator
from telegram.ext import Application, CommandHandler, ContextTypes

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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            tipo TEXT,
            vence DATE
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

# ========= COMANDOS =========
async def sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /sub [username] {días}")
        return
    
    username = context.args[0]
    try:
        dias = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Los días deben ser un número.")
        return

    user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    add_user(user.id, username, "premium", dias)

    fecha_vencimiento = (datetime.now() + timedelta(days=dias)).strftime("%d/%m/%Y")
    msg = (f"¡hola, {username}! se han añadido {dias} días a tu suscripción premium dentro de 𝔀inter 𝓹riv. ❤︎\n"
           f"🪽⊹ tu cupo vence el {fecha_vencimiento}")
    await update.message.reply_text(msg)

async def free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 1:
        await update.message.reply_text("Uso: /free [username]")
        return
    
    username = context.args[0]
    user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    add_user(user.id, username, "free")

    msg = (f"¡hola, {username}! eres cupo free dentro de 𝔀inter 𝓹riv. "
           "recuerda mandar un mínimo 4 referencias semanales para continuar con tu cupo. ❤︎")
    await update.message.reply_text(msg)

async def mod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 1:
        await update.message.reply_text("Uso: /mod [username]")
        return
    
    username = context.args[0]
    user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    add_user(user.id, username, "mod")

    msg = (f"¡hola, {username}! eres parte del staff en 𝔀inter 𝓹riv. "
           "tu cupo es ilimitado mientras seas parte de nuestra administración. ❤︎")
    await update.message.reply_text(msg)

async def addmod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Debes responder al mensaje del usuario que quieres hacer admin.")
        return

    user = update.message.reply_to_message.from_user
    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id,
            user.id,
            ChatAdministratorRights(
                is_anonymous=False,
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=False,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True
            )
        )
        await context.bot.set_chat_administrator_custom_title(
            update.effective_chat.id,
            user.id,
            "admin. ʚ"
        )
        add_user(user.id, user.username or user.full_name, "mod")
        await update.message.reply_text(f"{user.full_name} ahora es admin con título personalizado.")
    except Exception as e:
        await update.message.reply_text(f"Error al promover: {e}")

async def unmod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Debes responder al mensaje del usuario que quieres remover de admin.")
        return

    user = update.message.reply_to_message.from_user
    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id,
            user.id,
            ChatAdministratorRights(
                is_anonymous=False,
                can_manage_chat=False,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )
        )
        remove_user(user.id)
        await update.message.reply_text(f"{user.full_name} ha sido removido como admin y de la base de datos.")
    except Exception as e:
        await update.message.reply_text(f"Error al remover: {e}")

async def unsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Debes responder al mensaje del usuario que quieres dar de baja.")
        return

    user = update.message.reply_to_message.from_user
    try:
        remove_user(user.id)
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"{user.full_name} fue expulsado y removido de la base de datos.")
    except Exception as e:
        await update.message.reply_text(f"Error al expulsar: {e}")

async def mysub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sub = get_user(user.id)
    if not sub:
        await update.message.reply_text("No tienes ninguna suscripción activa.")
        return

    username, tipo, vence = sub
    if tipo == "premium":
        await update.message.reply_text(
            f"¡hola, {username}! eres cupo premium dentro de 𝔀inter 𝓹riv.\n"
            f"🪽⊹ tu cupo vence el {vence.strftime('%d/%m/%Y') if vence else 'desconocido'}"
        )
    elif tipo == "free":
        await update.message.reply_text(
            f"¡hola, {username}! eres cupo free dentro de 𝔀inter 𝓹riv. "
            "recuerda mandar un mínimo 4 referencias semanales para continuar con tu cupo."
        )
    elif tipo == "mod":
        await update.message.reply_text(
            f"¡hola, {username}! eres parte del staff en 𝔀inter 𝓹riv. "
            "tu cupo es ilimitado mientras seas parte de nuestra administración."
        )

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
                        f"¡holi! te recordamos que tu suscripción vence el día {fecha_venc.strftime('%d/%m/%Y')} "
                        "puedes contactar al propietario para volver a adquirir nuestros servicios. ♪"
                    )
                except:
                    pass

# ========= MAIN =========
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("sub", sub))
    app.add_handler(CommandHandler("free", free))
    app.add_handler(CommandHandler("mod", mod))
    app.add_handler(CommandHandler("addmod", addmod))
    app.add_handler(CommandHandler("unmod", unmod))
    app.add_handler(CommandHandler("unsub", unsub))
    app.add_handler(CommandHandler("mysub", mysub))

    # recordatorio 1 vez al día
    app.job_queue.run_repeating(reminder_job, interval=86400, first=10)

    print("Bot corriendo con WEBHOOK...")
    app.run_webhook(
        listen="0.0.0.0",
        port=WEBHOOK_PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
