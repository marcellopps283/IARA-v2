import logging
import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Setup basic logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")

ptb_app = None

import brain

async def start_command(update: Update, context):
    await update.message.reply_text(
        "🧠 IARA Core Online.\n"
        "Operando via VPS com roteamento multi-LLM.\n"
        "Manda qualquer mensagem!"
    )

async def handle_message(update: Update, context):
    """Route incoming messages through the brain pipeline."""
    user_text = update.message.text
    chat_id = update.message.chat.id
    logger.info(f"📩 [{chat_id}] {user_text[:80]}")

    # Show typing indicator while thinking
    await update.message.chat.send_action("typing")

    # Process through brain
    response = await brain.process(user_text, chat_id)

    # Send response (split if too long for Telegram's 4096 char limit)
    if len(response) <= 4096:
        await update.message.reply_text(response)
    else:
        # Split into chunks
        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i:i+4096])

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ptb_app
    logger.info("Starting IARA Core API Lifecycle...")

    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set in .env. Bot will not initialize.")
        yield
        return

    # Initialize PTB Application
    ptb_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Initialize and start the PTB application
    await ptb_app.initialize()

    # Determine if we use Webhook or Polling mode
    webhook_active = False
    if WEBHOOK_URL and "seudominio" not in WEBHOOK_URL:
        try:
            logger.info(f"Setting webhook URL to {WEBHOOK_URL}")
            await ptb_app.bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
            webhook_active = True
            logger.info("✅ Webhook configurado com sucesso!")
        except Exception as e:
            logger.warning(f"⚠️ Falha ao configurar webhook ({e}). Usando polling como fallback.")
    
    if not webhook_active:
        logger.info("🔄 Iniciando em modo POLLING (webhook não disponível).")
        # Delete any stale webhook before starting polling
        try:
            await ptb_app.bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass

    await ptb_app.start()

    if not webhook_active:
        # Start polling in the background
        await ptb_app.updater.start_polling(drop_pending_updates=True)
    
    yield  # Let FastAPI run and process HTTP requests
    
    # Shutdown PTB when FastAPI shuts down
    if ptb_app:
        logger.info("Shutting down Telegram bot...")
        try:
            if ptb_app.updater and ptb_app.updater.running:
                await ptb_app.updater.stop()
            await ptb_app.bot.delete_webhook()
        except Exception:
            pass
        await ptb_app.stop()
        await ptb_app.shutdown()

# Create FastAPI App
app = FastAPI(
    title="IARA Ecosystem",
    description="ZeroClaw-inspired Core API with Webhook Support",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    """Healthcheck endpoint for Docker Compose."""
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/webhook/bot1")
async def telegram_webhook(request: Request):
    """Endpoint that Telegram will hit with updates."""
    if not ptb_app:
        raise HTTPException(status_code=503, detail="Telegram bot not initialized")
    
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        # Push the update into PTB's processing queue
        await ptb_app.process_update(update)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}", exc_info=True)
        # Return 200 so Telegram doesn't retry infinitely on malformed updates
        return JSONResponse(content={"status": "error", "message": "Failed to process update"})

if __name__ == "__main__":
    import uvicorn
    # Local fallback testing
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
