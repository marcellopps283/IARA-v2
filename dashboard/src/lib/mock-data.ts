// Mock data matching real API schemas
// Used as fallback when API is not configured

import type { StatusResponse, MemoryExplorerResponse, LogEntry, ChatMessage } from "./types";

export const mockStatusResponse: StatusResponse = {
  system: {
    core: {
      status: "online",
      uptime: "2d 4h",
      version: "2.0.1",
    },
    infrastructure: {
      redis: { status: "online", latency_ms: 2 },
      qdrant: { status: "online", collections: ["mem0_core"] },
      infinity: { status: "online", model: "multilingual-e5-large" },
    },
    agents: {
      swarm: { status: "idle", active_tasks: 0 },
      council: { status: "ready" },
    },
    memory_metrics: {
      core_facts_count: 142,
      graph_nodes: 850,
    },
  },
};

export const mockMemoryExplorer: MemoryExplorerResponse = {
  working_memory: [
    { chat_id: "12345", last_message: "Analisando relatório trimestral Q4", updated_at: new Date().toISOString() },
    { chat_id: "12346", last_message: "Consulta sobre estratégia de investimento", updated_at: new Date(Date.now() - 3600000).toISOString() },
    { chat_id: "12347", last_message: "Revisão de código do pipeline ML", updated_at: new Date(Date.now() - 7200000).toISOString() },
  ],
  cognitive_memory: [
    { id: "mem_01", text: "Usuário prefere abordagem conservadora com foco em dividendos", user_id: "creator", created_at: "2026-03-10T14:30:00Z" },
    { id: "mem_02", text: "Respostas concisas com bullet points são preferidas", user_id: "creator", created_at: "2026-03-09T10:15:00Z" },
    { id: "mem_03", text: "Engenheiro de software sênior, familiarizado com Python e ML", user_id: "creator", created_at: "2026-03-08T16:45:00Z" },
    { id: "mem_04", text: "CTO de startup de fintech com 50 funcionários", user_id: "creator", created_at: "2026-03-07T09:00:00Z" },
  ],
  knowledge_graph: {
    total_nodes: 1250,
    total_edges: 4300,
    last_ingestion: "2d ago",
  },
};

// Log generation matching WS /ws/logs schema
const logModules = [
  "brain.memory_node",
  "brain.reasoning",
  "swarm.orchestrator",
  "council.consensus",
  "rag.lightrag",
  "infra.redis",
  "infra.qdrant",
  "embeddings.infinity",
];

const logMessages: Record<string, string[]> = {
  INFO: [
    "Agent pipeline initialized successfully",
    "Memory consolidation cycle completed",
    "Embedding batch processed: 128 vectors",
    "WebSocket connection established",
    "Council consensus reached in 340ms",
    "LightRAG index updated with 12 new nodes",
    "Core facts synced: 142 entries",
  ],
  WARNING: [
    "Qdrant latency above threshold: 45ms",
    "Memory buffer approaching capacity (87%)",
    "Retry attempt 2/3 for embedding service",
    "Token budget exceeded, truncating context",
  ],
  ERROR: [
    "Failed to connect to Qdrant cluster node 3",
    "LLM response timeout after 30000ms",
    "Invalid embedding dimension: expected 1024, got 768",
  ],
  CRITICAL: [
    "Service unresponsive for 60s, triggering failover",
    "Data corruption detected in memory store",
  ],
  DEBUG: [
    "Cache hit ratio: 0.89",
    "GC pause: 12ms",
    "Prompt tokens: 2048, Completion tokens: 512",
    "Vector similarity threshold: 0.82",
  ],
};

export function generateMockLog(): LogEntry {
  const levels: LogEntry["level"][] = ["INFO", "INFO", "INFO", "INFO", "WARNING", "WARNING", "DEBUG", "DEBUG", "ERROR", "CRITICAL"];
  const level = levels[Math.floor(Math.random() * levels.length)];
  const msgs = logMessages[level];
  return {
    timestamp: new Date().toISOString(),
    level,
    module: logModules[Math.floor(Math.random() * logModules.length)],
    message: msgs[Math.floor(Math.random() * msgs.length)],
  };
}

// Chat mock
const mockResponses = [
  "Com base na análise dos dados do **Q4**, identifiquei 3 pontos principais:\n\n1. **Receita** cresceu 23% YoY\n2. **Churn** reduziu de 4.2% para 3.1%\n3. **CAC** aumentou 15%, necessita atenção\n\n```python\ndf['growth_rate'] = df['revenue'].pct_change()\nprint(f'Média: {df[\"growth_rate\"].mean():.2%}')\n```\n\nRecomendo focar na otimização do funil de aquisição.",
  "Executei a busca vetorial no Qdrant e encontrei **12 documentos** relevantes com similaridade > 0.85.\n\nO contexto mais relevante vem do relatório `strategy_2025.pdf`, página 14:\n\n> *\"A estratégia de expansão deve priorizar mercados emergentes na América Latina...\"*\n\nDeseja que eu aprofunde em algum aspecto específico?",
  "O Council do Swarm chegou a um consenso em **340ms** com 3 agentes participando:\n\n- 🔍 **Analyst**: Confirmou tendência de alta\n- 📊 **Statistician**: p-value = 0.003 (significativo)\n- ✅ **Validator**: Dados consistentes com fontes externas\n\nConfiança geral: **94.2%**",
];

let chatId = 0;

export function getMockResponse(): string {
  return mockResponses[Math.floor(Math.random() * mockResponses.length)];
}

export function createChatMessage(role: "user" | "assistant", content: string): ChatMessage {
  return {
    id: `msg-${++chatId}`,
    role,
    content,
    timestamp: new Date().toISOString(),
  };
}

// Metric data for charts
export interface MetricPoint {
  timestamp: string;
  value: number;
}

export const mockLatencyData: MetricPoint[] = Array.from({ length: 24 }, (_, i) => ({
  timestamp: `${String(i).padStart(2, "0")}:00`,
  value: Math.floor(80 + Math.random() * 120),
}));

export const mockSuccessRateData: MetricPoint[] = Array.from({ length: 24 }, (_, i) => ({
  timestamp: `${String(i).padStart(2, "0")}:00`,
  value: Math.floor(85 + Math.random() * 15),
}));
