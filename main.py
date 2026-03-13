import logging
import os
import json
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
import ops_bot
import memory_manager
import memory
import settings_manager
import scheduler
from datetime import datetime
import time

# Uptime tracking
START_TIME = time.time()

# Dashboard Security
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "iara-secret-key")

# WebSocket active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# Custom Log Handler for WebSockets
class WebSocketLogHandler(logging.Handler):
    def __init__(self, manager: ConnectionManager):
        super().__init__()
        self.manager = manager
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    def emit(self, record):
        if not self.formatter:
            return
        log_entry = {
            "timestamp": self.formatter.formatTime(record, self.formatter.datefmt),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage()
        }
        # Safely broadcast to WebSockets
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.manager.broadcast(log_entry))
        except RuntimeError:
            pass # No running loop

# Add handler to root logger
ws_handler = WebSocketLogHandler(manager)
logging.getLogger().addHandler(ws_handler)

async def start_command(update: Update, context):
    await update.message.reply_text(
        "🧠 *IARA Core Online.*\n"
        "Operando via VPS com roteamento multi-LLM.\n"
        "Sociedade de Agentes ativa: Swarm + Council.\n\n"
        "Manda qualquer mensagem!",
        parse_mode="Markdown",
    )

async def handle_message(update: Update, context):
    """Route incoming messages through the brain pipeline with streaming UX."""
    user_text = update.message.text
    chat_id = update.message.chat.id
    logger.info(f"📩 [{chat_id}] {user_text[:80]}")

    # Send placeholder (edit-in-place streaming)
    # Intent is now resolved internally by brain.process() via Semantic Router
    placeholder = await update.message.reply_text("🧠 Processando...")

    # Process through brain
    try:
        response = await brain.process(user_text, chat_id)

        # Edit the placeholder with the real response
        response_str = str(response)
        if len(response_str) <= 4096:
            await placeholder.edit_text(response_str)
        else:
            # First chunk replaces placeholder, rest are new messages
            await placeholder.edit_text(response_str[:4096])
            for i in range(4096, len(response_str), 4096):
                await update.message.reply_text(response_str[i:i+4096])

    except Exception as e:
        logger.error(f"❌ handle_message error: {e}", exc_info=True)
        await placeholder.edit_text(f"❌ Erro: {str(e)[:200]}")
        await ops_bot.log_error(e, f"Chat {chat_id}: {user_text[:100]}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ptb_app
    logger.info("Starting IARA Core API Lifecycle...")

    # Initialize memory stack (Redis)
    import memory
    await memory.init()
    
    # 🚀 Warm up semantic engines (Embeddings, Mem0, LightRAG) - SOTA 2026
    logger.info("🔥 Phase 12: Starting Warmup Blitz...")
    try:
        # Start Autonomous Scheduler (Phase 14)
        await scheduler.start()
        
        # Pre-warm embeddings
        import semantic_router
        await semantic_router.get_embedding("warmup query for latency")
        
        # Pre-warm LLM connection pools (Groq/Cerebras)
        router = brain.get_router()
        await asyncio.gather(
            router.generate([{"role": "user", "content": "hi"}], task_type="chat_fast"),
            return_exceptions=True
        )
        
        # Pre-connect Redis
        r = memory.get_redis()
        await r.ping()
        
        logger.info("✅ Warmup complete. Systems primed.")
    except Exception as e:
        logger.warning(f"⚠️ Warmup blitz failed: {e}")
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

    # Notify ops bot
    await ops_bot.log_startup()

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

    # Stop Scheduler
    await scheduler.stop()

# Create FastAPI App
app = FastAPI(
    title="IARA Ecosystem",
    description="ZeroClaw-inspired Core API with Dashboard Support",
    version="1.1.0",
    lifespan=lifespan
)

# CORS for Lovable/Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dashboard Frontend Serving
DASHBOARD_PATH = os.path.join(os.getcwd(), "dashboard", "dist")

if os.path.exists(DASHBOARD_PATH):
    # Mount static assets (JS, CSS, images)
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_PATH, html=True), name="dashboard")

    # SPA Catch-all: Redirect all /dashboard/* routes to dashboard/index.html
    @app.get("/dashboard/{full_path:path}")
    async def serve_dashboard(request: Request, full_path: str):
        index_path = os.path.join(DASHBOARD_PATH, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return JSONResponse({"error": "Dashboard index.html not found"}, status_code=404)
else:
    logger.warning(f"⚠️ Dashboard dist folder not found at {DASHBOARD_PATH}. Frontend will not be served.")

async def verify_api_key(request: Request):
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if api_key != DASHBOARD_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid API Key")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SSE Streaming Endpoint (SOTA 2026)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def token_stream_generator(text: str, chat_id: int):
    """Generates SSE formatted tokens from the brain stream."""
    try:
        async for token in brain.process_stream(text, chat_id):
            # Clean for SSE formatting
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"❌ SSE Generator error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.get("/api/chat/stream")
async def chat_stream(text: str, chat_id: int = 0, api_key: str = None):
    """
    Streaming chat endpoint for web/dashboard.
    Returns a text/event-stream.
    """
    if api_key != DASHBOARD_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    return StreamingResponse(
        token_stream_generator(text, chat_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
            "Connection": "keep-alive",
        }
    )

@app.get("/health")
async def health_check():
    """Healthcheck endpoint for Docker Compose."""
    return {"status": "healthy", "version": "1.1.0"}

@app.get("/status")
async def get_status(request: Request):
    await verify_api_key(request)
    
    # Check Infrastructure
    redis_status = "offline"
    redis_latency = 0
    try:
        r = memory.get_redis()
        start = time.time()
        await r.ping()
        redis_latency = int((time.time() - start) * 1000)
        redis_status = "online"
    except Exception:
        pass

    qdrant_status = "offline"
    collections = []
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(host=os.getenv("QDRANT_HOST", "qdrant"), port=6333)
        cols = qc.get_collections().collections
        collections = [c.name for c in cols]
        qdrant_status = "online"
    except Exception:
        pass

    infinity_status = "offline"
    try:
        import httpx
        from config import TEI_URL
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{TEI_URL}/health")
            if resp.status_code == 200:
                infinity_status = "online"
    except Exception:
        pass

    # Uptime
    uptime_seconds = int(time.time() - START_TIME)
    days, rem = divmod(uptime_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    uptime_str = f"{days}d {hours}h {minutes}m"

    # Memory Metrics
    facts_count = 0
    try:
        # Get count from Mem0 (heuristic: search all)
        mem0 = memory_manager.get_mem0()
        search_res = mem0.search("", limit=1000)
        facts_count = len(search_res) if search_res else 0
    except Exception:
        pass

    return {
        "system": {
            "core": {
                "status": "online", 
                "uptime": uptime_str,
                "version": "1.1.0"
            },
            "infrastructure": {
                "redis": {"status": redis_status, "latency_ms": redis_latency},
                "qdrant": {"status": qdrant_status, "collections": collections},
                "infinity": {"status": infinity_status, "model": os.getenv("TEI_MODEL", "unknown")}
            },
            "agents": {
                "swarm": {"status": "idle", "active_tasks": 0},
                "council": {"status": "ready"}
            },
            "memory_metrics": {
                "core_facts_count": facts_count,
                "graph_nodes": 0 # TODO: Stats from LightRAG
            }
        }
    }

@app.patch("/settings")
async def update_settings_endpoint(request: Request):
    await verify_api_key(request)
    data = await request.json()
    new_settings = await settings_manager.update_settings(data)
    return {"status": "success", "updated": new_settings}

@app.get("/memory/explorer")
async def memory_explorer(request: Request):
    await verify_api_key(request)
    
    # 1. Working Memory (Redis)
    r = memory.get_redis()
    keys = await r.keys("iara:conv:*")
    working_memory = []
    for k in keys[:10]: # Limit for performance
        messages = await r.lrange(k, -1, -1) # Last message
        if messages:
            try:
                msg_data = json.loads(messages[0])
                working_memory.append({
                    "chat_id": k.split(":")[-1],
                    "last_message": msg_data.get("content", ""),
                    "updated_at": msg_data.get("ts", "")
                })
            except Exception:
                continue

    # 2. Cognitive Memory (Mem0)
    cognitive_memory = []
    try:
        mem0 = memory_manager.get_mem0()
        facts = mem0.search("", limit=20)
        for f in facts:
            cognitive_memory.append({
                "id": f.get("id", "unknown"),
                "text": f.get("memory", ""),
                "user_id": f.get("user_id", "creator"),
                "created_at": f.get("created_at", "")
            })
    except Exception:
        pass

    return {
        "working_memory": working_memory,
        "cognitive_memory": cognitive_memory,
        "knowledge_graph": {
            "total_nodes": 0,
            "total_edges": 0,
            "last_ingestion": "never"
        }
    }

@app.post("/memory/working/reset")
async def reset_working_memory_endpoint(request: Request):
    await verify_api_key(request)
    r = memory.get_redis()
    keys = await r.keys("iara:conv:*")
    if keys:
        await r.delete(*keys)
    logger.info("🧹 Working memory reset via dashboard")
    return {"status": "success", "message": f"{len(keys)} sessions cleared"}

@app.get("/memory/facts")
async def list_facts(request: Request):
    await verify_api_key(request)
    mem0 = memory_manager.get_mem0()
    results = mem0.get_all(user_id="creator")
    return results

@app.delete("/memory/facts/{fact_id}")
async def delete_fact_endpoint(fact_id: str, request: Request):
    await verify_api_key(request)
    mem0 = memory_manager.get_mem0()
    mem0.delete(fact_id)
    return {"status": "success"}

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    # API Key check via query param for WS
    token = websocket.query_params.get("api_key")
    if token != DASHBOARD_API_KEY:
        await websocket.close(code=4033)
        return
        
    await manager.connect(websocket)
    try:
        while True:
            # We just need to keep the connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

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
