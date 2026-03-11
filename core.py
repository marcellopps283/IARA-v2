"""
core.py — Memória em 3 camadas (Working, Episodic, Core)
Gerencia toda a persistência de estado da Kitty via SQLite.
"""

import aiosqlite
import json
import logging
import asyncio
from datetime import datetime

import config
import embeddings

logger = logging.getLogger("core")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Inicialização do banco de dados
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def init_db():
    """Cria as 3 tabelas de memória se não existirem."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        # Working Memory — conversas ativas (curto prazo)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS working_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Episodic Memory — resumos de conversas passadas (médio prazo)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                tags TEXT DEFAULT '',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Core Memory — fatos permanentes sobre o usuário (longo prazo)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS core_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Swarm Jobs (Persistência da fila do Orquestrador contra Crash/Amnésia)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS swarm_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Stateful Todo Machine (Phase 1)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # MCP Servers Registry (Phase 17)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mcp_servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                api_key TEXT,
                status TEXT DEFAULT 'offline',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Phase 12 - Project Isolation
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Schema Migrations: Adiciona project_id e embedding nas memórias existentes
        # Como SQLite não tem "ADD COLUMN IF NOT EXISTS", capturamos o erro
        tables_to_migrate = ["working_memory", "episodic_memory", "core_memory"]
        for table in tables_to_migrate:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN project_id INTEGER DEFAULT NULL")
            except aiosqlite.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    logger.warning(f"Erro ao migrar tabela {table}: {e}")
            
            # Trabalharemos com BLOB (bytes) para guardar arrays do embedding
            try:
                if table in ["episodic_memory", "core_memory"]:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN embedding BLOB DEFAULT NULL")
            except aiosqlite.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    logger.warning(f"Erro ao adicionar embedding na tabela {table}: {e}")

        await db.commit()
        logger.info("✅ Banco de dados inicializado com 5 tabelas centrais + schema de Projetos.")

    # Criar tabela de lembretes separadamente (migration segura)
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                trigger_time DATETIME NOT NULL,
                sent BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela de auto-reflexões
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela do Agendador Autônomo (Phase 14)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                cron TEXT NOT NULL,
                action TEXT NOT NULL,
                params TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                last_run DATETIME DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# App Config & Project Config
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_app_config(key: str) -> str | None:
    """Recupera um valor de configuração global do banco."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute("SELECT value FROM app_config WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def set_app_config(key: str, value: str):
    """Define um valor de configuração global no banco."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        await db.execute(
            "INSERT INTO app_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=?",
            (key, value, value)
        )
        await db.commit()

async def get_or_create_project(name: str) -> int:
    """Busca um projeto pelo nome. Se não existir, cria-o e retorna o novo ID."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute("SELECT id FROM projects WHERE name = ?", (name,))
        row = await cursor.fetchone()
        if row:
            return row[0]
            
        cursor = await db.execute("INSERT INTO projects (name) VALUES (?)", (name,))
        await db.commit()
        return cursor.lastrowid

async def get_project_name(project_id: int) -> str | None:
    """Retorna o nome do projeto dado o seu ID."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute("SELECT name FROM projects WHERE id = ?", (project_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def get_all_projects() -> list[dict]:
    """Retorna a lista de todos os projetos cadastrados."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute("SELECT id, name, description, created_at FROM projects ORDER BY name ASC")
        rows = await cursor.fetchall()
        return [{"id": r[0], "name": r[1], "description": r[2], "created_at": r[3]} for r in rows]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Working Memory — Conversa atual (RAM da Kitty)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def save_message(role: str, content: str, project_id: int | None = None):
    """Salva uma mensagem na working memory."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        await db.execute(
            "INSERT INTO working_memory (role, content, project_id) VALUES (?, ?, ?)",
            (role, content, project_id)
        )
        await db.commit()


async def get_conversation(limit: int = None, project_id: int | None = None) -> list[dict]:
    """
    Retorna o histórico de conversas recente.
    Se limit for None, usa MAX_WORKING_MEMORY do config.
    """
    if limit is None:
        limit = config.MAX_WORKING_MEMORY

    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if project_id is not None:
            cursor = await db.execute(
                "SELECT role, content FROM working_memory WHERE project_id = ? OR project_id IS NULL ORDER BY id DESC LIMIT ?",
                (project_id, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT role, content FROM working_memory WHERE project_id IS NULL ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        rows = await cursor.fetchall()

    # Retorna em ordem cronológica (mais antigo primeiro)
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


async def get_working_memory_count(project_id: int | None = None) -> int:
    """Conta quantas mensagens tem na working memory."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if project_id is not None:
            cursor = await db.execute("SELECT COUNT(*) FROM working_memory WHERE project_id = ? OR project_id IS NULL", (project_id,))
        else:
            cursor = await db.execute("SELECT COUNT(*) FROM working_memory WHERE project_id IS NULL")
        row = await cursor.fetchone()
    return row[0]


async def compact_working_memory(summary: str, project_id: int | None = None):
    """
    Compacta working memory:
    1. Salva um resumo na episodic memory
    2. Limpa a working memory (mantém últimas 4 mensagens)
    """
    # Salvar resumo na episodic propagando o project_id
    await save_episode(summary, tags="", project_id=project_id)

    # Manter apenas as últimas 4 mensagens
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if project_id is not None:
            await db.execute("""
                DELETE FROM working_memory WHERE id NOT IN (
                    SELECT id FROM working_memory WHERE project_id = ? OR project_id IS NULL ORDER BY id DESC LIMIT 4
                ) AND (project_id = ? OR project_id IS NULL)
            """, (project_id, project_id))
        else:
            await db.execute("""
                DELETE FROM working_memory WHERE id NOT IN (
                    SELECT id FROM working_memory WHERE project_id IS NULL ORDER BY id DESC LIMIT 4
                ) AND project_id IS NULL
            """)
        await db.commit()

    logger.info("📦 Working memory compactada. Resumo salvo na episodic.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Episodic Memory — Conversas passadas (HD da Kitty)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _background_embed_episode(episode_id: int, summary: str):
    """Gera e salva o embedding de um episódio de forma assíncrona (não-bloqueante)."""
    vector = await embeddings.generate_embedding(summary)
    if vector:
        blob = embeddings.serialize_embedding(vector)
        async with aiosqlite.connect(str(config.DB_PATH)) as db:
            await db.execute("UPDATE episodic_memory SET embedding = ? WHERE id = ?", (blob, episode_id))
            await db.commit()

async def save_episode(summary: str, tags: str = "", project_id: int | None = None):
    """Salva um resumo de conversa na episodic memory."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute(
            "INSERT INTO episodic_memory (summary, tags, project_id) VALUES (?, ?, ?)",
            (summary, tags, project_id)
        )
        episode_id = cursor.lastrowid
        await db.commit()
        
    # Dispara a geração do embedding sem bloquear o turno
    asyncio.create_task(_background_embed_episode(episode_id, summary))


async def get_episode_count() -> int:
    """Conta quantos episódios existem."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM episodic_memory")
        row = await cursor.fetchone()
    return row[0]


async def get_all_episodes(limit: int = 20, project_id: int | None = None) -> list[str]:
    """Retorna os resumos mais recentes como lista de strings."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if project_id is not None:
            cursor = await db.execute(
                "SELECT summary FROM episodic_memory WHERE project_id = ? OR project_id IS NULL ORDER BY id DESC LIMIT ?",
                (project_id, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT summary FROM episodic_memory WHERE project_id IS NULL ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        rows = await cursor.fetchall()
    return [r[0] for r in reversed(rows)]


async def get_recent_episodes(limit: int = 5, project_id: int | None = None) -> list[dict]:
    """Retorna os episódios mais recentes."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if project_id is not None:
            cursor = await db.execute(
                "SELECT summary, tags, timestamp FROM episodic_memory WHERE project_id = ? OR project_id IS NULL ORDER BY id DESC LIMIT ?",
                (project_id, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT summary, tags, timestamp FROM episodic_memory WHERE project_id IS NULL ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        rows = await cursor.fetchall()

    return [
        {"summary": r[0], "tags": r[1], "timestamp": r[2]}
        for r in reversed(rows)
    ]

async def get_semantic_episodes(query_embedding: list[float], limit: int = 3, project_id: int | None = None) -> list[dict]:
    """
    Retorna os episódios mais semanticamente relevantes usando Cosine Similarity.
    Se falhar, retorna os mais recentes.
    """
    if not query_embedding:
        # Fallback silencioso para ordenação temporal
        return await get_recent_episodes(limit, project_id)

    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if project_id is not None:
            cursor = await db.execute(
                "SELECT summary, tags, timestamp, embedding FROM episodic_memory WHERE project_id = ? OR project_id IS NULL",
                (project_id,)
            )
        else:
            cursor = await db.execute(
                "SELECT summary, tags, timestamp, embedding FROM episodic_memory WHERE project_id IS NULL"
            )
        rows = await cursor.fetchall()

    scored_episodes = []
    for r in rows:
        summary, tags, timestamp, blob = r
        if not blob:
            continue
        
        vec = embeddings.deserialize_embedding(blob)
        if not vec:
            continue
            
        score = embeddings.cosine_similarity(query_embedding, vec)
        scored_episodes.append({
            "summary": summary,
            "tags": tags,
            "timestamp": timestamp,
            "score": score
        })

    # Sort descending by score
    scored_episodes.sort(key=lambda x: x["score"], reverse=True)
    return scored_episodes[:limit]

async def search_episodes(query: str, limit: int = 3) -> list[dict]:
    """Busca episódios por palavra-chave (busca simples em texto)."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT summary, tags, timestamp FROM episodic_memory WHERE summary LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit)
        )
        rows = await cursor.fetchall()

    return [
        {"summary": r[0], "tags": r[1], "timestamp": r[2]}
        for r in rows
    ]

async def get_unprocessed_episodes(limit: int = 50) -> list[dict]:
    """Retorna os episódios mais antigos para consolidação na core memory."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT id, summary, timestamp FROM episodic_memory ORDER BY id ASC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        
    return [
        {"id": r[0], "summary": r[1], "timestamp": r[2]}
        for r in rows
    ]

async def delete_old_episodes(ids: list[int]):
    """Remove episódios após a consolidação."""
    if not ids: return
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        # Usa placeholdering pro IN clause
        placeholders = ",".join("?" * len(ids))
        await db.execute(f"DELETE FROM episodic_memory WHERE id IN ({placeholders})", ids)
        await db.commit()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Core Memory — Fatos permanentes (Alma da Kitty)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _background_embed_core_fact(fact_id: int, content: str):
    """Gera e salva o embedding de um fato permanente de forma assíncrona."""
    vector = await embeddings.generate_embedding(content)
    if vector:
        blob = embeddings.serialize_embedding(vector)
        async with aiosqlite.connect(str(config.DB_PATH)) as db:
            await db.execute("UPDATE core_memory SET embedding = ? WHERE id = ?", (blob, fact_id))
            await db.commit()

async def save_core_fact(category: str, content: str, confidence: float = 1.0, project_id: int | None = None):
    """
    Salva um fato permanente na core memory.
    Se o fato já existir (mesmo conteúdo e projeto), atualiza a confiança.
    """
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        # Verifica se já existe para o mesmo projeto
        if project_id is not None:
            cursor = await db.execute(
                "SELECT id FROM core_memory WHERE content = ? AND project_id = ?", (content, project_id)
            )
        else:
            cursor = await db.execute(
                "SELECT id FROM core_memory WHERE content = ? AND project_id IS NULL", (content,)
            )
        
        existing = await cursor.fetchone()

        if existing:
            fact_id = existing[0]
            await db.execute(
                "UPDATE core_memory SET confidence = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (confidence, fact_id)
            )
        else:
            cursor = await db.execute(
                "INSERT INTO core_memory (category, content, confidence, project_id) VALUES (?, ?, ?, ?)",
                (category, content, confidence, project_id)
            )
            fact_id = cursor.lastrowid

        await db.commit()

    # Dispara a geração assíncrona do embedding
    asyncio.create_task(_background_embed_core_fact(fact_id, content))


async def get_core_memory(project_id: int | None = None) -> list[dict]:
    """Retorna todos os fatos da core memory do projeto, ordenados por confiança."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if project_id is not None:
            cursor = await db.execute(
                "SELECT category, content, confidence, updated_at FROM core_memory WHERE project_id = ? OR project_id IS NULL ORDER BY confidence DESC",
                (project_id,)
            )
        else:
            cursor = await db.execute(
                "SELECT category, content, confidence, updated_at FROM core_memory WHERE project_id IS NULL ORDER BY confidence DESC"
            )
        rows = await cursor.fetchall()

    return [
        {
            "category": r[0],
            "content": r[1],
            "confidence": r[2],
            "updated_at": r[3],
        }
        for r in rows
    ]


async def get_core_memory_text(project_id: int | None = None) -> str:
    """Retorna a core memory formatada como texto para injetar no prompt."""
    facts = await get_core_memory(project_id=project_id)
    if not facts:
        return "Ainda não conheço fatos permanentes sobre o Criador no contexto deste projeto."

    lines = []
    for f in facts:
        lines.append(f"- [{f['category']}] {f['content']}")

    return "\n".join(lines)


async def get_semantic_core_facts(query_embedding: list[float], limit: int = 5, project_id: int | None = None) -> list[dict]:
    """
    Retorna os fatos permanentes mais relevantes.
    Se não houver embedding, retorna ordenado por confiança (padrão).
    """
    if not query_embedding:
        facts = await get_core_memory(project_id)
        return facts[:limit]
        
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if project_id is not None:
            cursor = await db.execute(
                "SELECT category, content, confidence, updated_at, embedding FROM core_memory WHERE project_id = ? OR project_id IS NULL",
                (project_id,)
            )
        else:
            cursor = await db.execute(
                "SELECT category, content, confidence, updated_at, embedding FROM core_memory WHERE project_id IS NULL"
            )
        rows = await cursor.fetchall()

    scored_facts = []
    for r in rows:
        category, content, conf, updated_at, blob = r
        score = 0
        if blob:
            vec = embeddings.deserialize_embedding(blob)
            if vec:
                score = embeddings.cosine_similarity(query_embedding, vec)
        
        # Combinar Score + Confidence (Opcional, mas útil)
        final_score = score * conf
        scored_facts.append({
            "category": category,
            "content": content,
            "confidence": conf,
            "updated_at": updated_at,
            "score": final_score
        })

    scored_facts.sort(key=lambda x: x["score"], reverse=True)
    return scored_facts[:limit]


async def delete_core_fact(content: str, project_id: int | None = None):
    """Remove um fato da core memory no escopo do projeto."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if project_id is not None:
            await db.execute(
                "DELETE FROM core_memory WHERE content = ? AND project_id = ?", (content, project_id)
            )
        else:
            await db.execute(
                "DELETE FROM core_memory WHERE content = ? AND project_id IS NULL", (content,)
            )
        await db.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Reminders — Lembretes agendados
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def save_reminder(message: str, trigger_time: datetime) -> int:
    """Salva um lembrete e retorna o ID."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute(
            "INSERT INTO reminders (message, trigger_time) VALUES (?, ?)",
            (message, trigger_time.isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_reminders() -> list[dict]:
    """Retorna lembretes pendentes que já passaram do horário."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT id, message, trigger_time FROM reminders WHERE sent = 0 AND trigger_time <= ?",
            (now,)
        )
        rows = await cursor.fetchall()

    return [{"id": r[0], "message": r[1], "trigger_time": r[2]} for r in rows]


async def mark_reminder_sent(reminder_id: int):
    """Marca um lembrete como enviado."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        await db.execute(
            "UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,)
        )
        await db.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Auto-Reflexão — Lições aprendidas
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def save_reflection(lesson: str):
    """Salva uma lição de auto-reflexão."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        await db.execute(
            "INSERT INTO reflections (lesson) VALUES (?)", (lesson,)
        )
        # Manter apenas as 5 mais recentes
        await db.execute("""
            DELETE FROM reflections WHERE id NOT IN (
                SELECT id FROM reflections ORDER BY id DESC LIMIT 5
            )
        """)
        await db.commit()


async def get_active_reflections() -> list[str]:
    """Retorna as 5 reflexões mais recentes."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT lesson FROM reflections ORDER BY id DESC LIMIT 5"
        )
        rows = await cursor.fetchall()
    return [r[0] for r in reversed(rows)]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Weather — Clima via Open-Meteo (grátis, sem API key)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_weather(lat: float = -23.55, lon: float = -46.63) -> str:
    """
    Busca clima atual via Open-Meteo API.
    Default: São Paulo (pode ser alterado via core memory).
    """
    import aiohttp
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
            f"&timezone=America/Sao_Paulo"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return "Não consegui acessar os dados de clima."
                data = await resp.json()

        current = data.get("current", {})
        temp = current.get("temperature_2m", "?")
        humidity = current.get("relative_humidity_2m", "?")
        wind = current.get("wind_speed_10m", "?")
        code = current.get("weather_code", 0)

        # Traduzir weather code
        weather_desc = _weather_code_to_text(code)

        return (
            f"Clima atual:\n"
            f"- Temperatura: {temp}°C\n"
            f"- Umidade: {humidity}%\n"
            f"- Vento: {wind} km/h\n"
            f"- Condição: {weather_desc}"
        )
    except Exception as e:
        return f"Erro ao buscar clima: {e}"


def _weather_code_to_text(code: int) -> str:
    """Traduz WMO weather code para texto."""
    codes = {
        0: "Céu limpo", 1: "Praticamente limpo", 2: "Parcialmente nublado",
        3: "Nublado", 45: "Nevoeiro", 48: "Nevoeiro com geada",
        51: "Garoa leve", 53: "Garoa moderada", 55: "Garoa forte",
        61: "Chuva leve", 63: "Chuva moderada", 65: "Chuva forte",
        71: "Neve leve", 73: "Neve moderada", 75: "Neve forte",
        80: "Pancadas leves", 81: "Pancadas moderadas", 82: "Pancadas fortes",
        95: "Tempestade", 96: "Tempestade com granizo leve", 99: "Tempestade com granizo",
    }
    return codes.get(code, f"Código {code}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# System Status — Info do dispositivo (Termux)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_system_status() -> str:
    """Retorna status do sistema via Termux API."""
    import subprocess
    import json as json_mod
    parts = []

    # Bateria
    try:
        res = subprocess.run(
            ["termux-battery-status"], capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            bat = json_mod.loads(res.stdout)
            parts.append(f"Bateria: {bat.get('percentage', '?')}% ({bat.get('status', '?')})")
    except Exception:
        parts.append("Bateria: indisponível (sem Termux API)")

    # Storage
    try:
        res = subprocess.run(
            ["df", "-h", "/data"], capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            lines = res.stdout.strip().split("\n")
            if len(lines) > 1:
                cols = lines[1].split()
                parts.append(f"Storage: {cols[2]} usado / {cols[1]} total ({cols[4]} ocupado)")
    except Exception:
        parts.append("Storage: indisponível")

    # Uptime
    try:
        res = subprocess.run(
            ["uptime", "-p"], capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            parts.append(f"Uptime: {res.stdout.strip()}")
    except Exception:
        pass

    # RAM
    try:
        res = subprocess.run(
            ["free", "-m"], capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            lines = res.stdout.strip().split("\n")
            if len(lines) > 1:
                cols = lines[1].split()
                # Mem: total used free shared buffers cached
                parts.append(f"RAM: {cols[2]}MB usado / {cols[1]}MB total")
    except Exception:
        pass

    # CPU
    try:
        res = subprocess.run(
            ["top", "-n", "1", "-m", "1"], capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            for line in res.stdout.split("\n"):
                if line.startswith("User"):
                    parts.append(f"CPU: {line.strip()}")
                    break
    except Exception:
        pass

    return "\n  ".join(parts) if parts else "Status do sistema indisponível."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Hardware Control (Cyber-Mãos)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def turn_on_flashlight(on: bool = True) -> str:
    """Acende ou apaga a lanterna do dispositivo via termux-torch."""
    import subprocess
    cmd = "on" if on else "off"
    try:
        res = subprocess.run(
            ["termux-torch", cmd], capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            return f"Lanterna {'ligada' if on else 'desligada'} com sucesso."
        return f"Falha ao controlar lanterna: {res.stderr}"
    except Exception as e:
        return f"Erro ao acessar termux-torch: {e}"


async def get_location() -> str:
    """Pega a localização atual do GPS."""
    import subprocess
    import json as json_mod
    try:
        res = subprocess.run(
            ["termux-location", "-p", "network", "-r", "once"], capture_output=True, text=True, timeout=10
        )
        if res.returncode == 0:
            loc = json_mod.loads(res.stdout)
            lat = loc.get("latitude", "?")
            lon = loc.get("longitude", "?")
            return f"Localização atual: Latitude {lat}, Longitude {lon} (https://maps.google.com/?q={lat},{lon})"
        return f"Falha ao obter localização: {res.stderr}"
    except Exception as e:
        return f"Erro ao acessar termux-location: {e}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# File I/O — Kitty Shadow (workspace de arquivos)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def write_to_shadow(filename: str, content: str) -> str:
    """Salva arquivo no Kitty_Shadow (pasta de trabalho)."""
    config.SHADOW_DIR.mkdir(exist_ok=True)
    filepath = config.SHADOW_DIR / filename
    filepath.write_text(content, encoding="utf-8")
    return str(filepath)


async def read_file(filename: str) -> str:
    """Lê arquivo do Kitty_Shadow."""
    filepath = config.SHADOW_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return f"Arquivo '{filename}' não encontrado."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Identity — Carrega SOUL/STYLE/SKILLS do disco
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_identity() -> str:
    """
    Carrega os arquivos de identidade (SOUL.md, STYLE.md, SKILLS.md)
    e os concatena para injeção no system prompt.
    """
    identity_parts = []

    for filename in ["SOUL.md", "STYLE.md", "SKILLS.md"]:
        filepath = config.IDENTITY_DIR / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            identity_parts.append(content)
        else:
            logger.warning(f"⚠️ Arquivo de identidade não encontrado: {filepath}")

    return "\n\n---\n\n".join(identity_parts)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Gerenciamento de Fila Swarm (Anti-Crash)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def add_swarm_job(role_name: str, payload: str) -> int:
    """Insere um novo job pendente na fila do BD."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute(
            "INSERT INTO swarm_jobs (role_name, payload) VALUES (?, ?)",
            (role_name, payload)
        )
        await db.commit()
        return cursor.lastrowid

async def get_pending_swarm_jobs() -> list[dict]:
    """Retorna todos os jobs pending ou processing (recuperação pós-crash)."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM swarm_jobs WHERE status IN ('pending', 'processing') ORDER BY created_at ASC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def update_swarm_job_status(job_id: int, status: str, result: str = None):
    """Atualiza o status (e resultado opcional) de um job no banco."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        if result is not None:
            await db.execute(
                "UPDATE swarm_jobs SET status = ?, result = ? WHERE id = ?",
                (status, result, job_id)
            )
        else:
            await db.execute(
                "UPDATE swarm_jobs SET status = ? WHERE id = ?",
                (status, job_id)
            )
        await db.commit()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stateful Todo Machine (Fase 1)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def add_task_state(description: str) -> int:
    """Cria uma tarefa (TODO) no bd."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute("INSERT INTO tasks_state (description) VALUES (?)", (description,))
        await db.commit()
        return cursor.lastrowid

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Background Scheduler (Phase 14)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def add_scheduled_job(name: str, cron: str, action: str, params: dict | None = None, enabled: bool = True) -> int:
    """Insere ou atualiza um job autônomo na tabela."""
    import json
    params_str = json.dumps(params or {})
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute("""
            INSERT INTO scheduled_jobs (name, cron, action, params, enabled)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                cron = excluded.cron,
                action = excluded.action,
                params = excluded.params,
                enabled = excluded.enabled
        """, (name, cron, action, params_str, 1 if enabled else 0))
        await db.commit()
        return cursor.lastrowid

async def get_all_scheduled_jobs() -> list[dict]:
    """Retorna a lista completas de jobs configurados."""
    import json
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM scheduled_jobs ORDER BY id ASC")
        rows = await cursor.fetchall()
        jobs = []
        for r in rows:
            d = dict(r)
            d["params"] = json.loads(d["params"])
            d["enabled"] = bool(d["enabled"])
            jobs.append(d)
        return jobs

async def update_job_last_run(job_id: int):
    """Atualiza o stamp de última execução de um job."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        await db.execute("UPDATE scheduled_jobs SET last_run = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
        await db.commit()

async def toggle_job(name: str) -> bool:
    """Inverte o status ativo/inativo de um job. Retorna o novo estado."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute("SELECT enabled FROM scheduled_jobs WHERE name = ?", (name,))
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Job '{name}' não encontrado.")
        new_state = 0 if row[0] else 1
        await db.execute("UPDATE scheduled_jobs SET enabled = ? WHERE name = ?", (new_state, name))
        await db.commit()
        return bool(new_state)

async def delete_scheduled_job(name: str) -> bool:
    """Deleta permanentemente um job do banco."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        cursor = await db.execute("DELETE FROM scheduled_jobs WHERE name = ?", (name,))
        await db.commit()
        return cursor.rowcount > 0

async def get_active_task() -> dict | None:
    """Busca a única tarefa permitida em in_progress."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks_state WHERE status = 'in_progress'")
        row = await cursor.fetchone()
        return dict(row) if row else None

async def _get_all_tasks() -> list[dict]:
    """Retorna todas as tarefas (pending, in_progress, completed) para o scheduler montar briefs."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks_state ORDER BY id ASC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def set_task_status(task_id: int, status: str):
    """Atualiza o status de uma tarefa na máquina de estados."""
    async with aiosqlite.connect(str(config.DB_PATH)) as db:
        await db.execute(
            "UPDATE tasks_state SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, task_id)
        )
        await db.commit()
