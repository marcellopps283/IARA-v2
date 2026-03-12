// API types matching real FastAPI endpoints

// GET /status
export interface StatusResponse {
  system: {
    core: {
      status: string;
      uptime: string;
      version: string;
    };
    infrastructure: {
      redis: {
        status: string;
        latency_ms: number;
      };
      qdrant: {
        status: string;
        collections: string[];
      };
      infinity: {
        status: string;
        model: string;
      };
    };
    agents: {
      swarm: {
        status: string;
        active_tasks: number;
      };
      council: {
        status: string;
      };
    };
    memory_metrics: {
      core_facts_count: number;
      graph_nodes: number;
    };
  };
}

// WS /ws/logs
export interface LogEntry {
  timestamp: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  module: string;
  message: string;
}

// GET /memory/explorer
export interface MemoryExplorerResponse {
  working_memory: WorkingMemoryItem[];
  cognitive_memory: CognitiveMemoryItem[];
  knowledge_graph: {
    total_nodes: number;
    total_edges: number;
    last_ingestion: string;
  };
}

export interface WorkingMemoryItem {
  chat_id: string;
  last_message: string;
  updated_at: string;
}

export interface CognitiveMemoryItem {
  id: string;
  text: string;
  user_id: string;
  created_at: string;
}

// Chat messages (local type)
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  images?: string[]; // base64 or URLs of attached images
}

// Chat options
export type ReasoningMode = "fast" | "planning";

