import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Search, Brain, Cpu, Network, MessageSquare } from "lucide-react";
import { fetchMemoryExplorer, isApiConfigured } from "@/lib/api-client";
import { mockMemoryExplorer } from "@/lib/mock-data";
import type { MemoryExplorerResponse } from "@/lib/types";

type Tab = "working" | "cognitive" | "graph";

export default function MemoryPage() {
  const [activeTab, setActiveTab] = useState<Tab>("working");
  const [search, setSearch] = useState("");
  const [data, setData] = useState<MemoryExplorerResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      if (!isApiConfigured()) {
        setData(mockMemoryExplorer);
        setLoading(false);
        return;
      }
      try {
        const res = await fetchMemoryExplorer();
        setData(res);
      } catch {
        setData(mockMemoryExplorer);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "working", label: "Working", icon: <Cpu className="h-3.5 w-3.5" /> },
    { id: "cognitive", label: "Cognitive", icon: <Brain className="h-3.5 w-3.5" /> },
    { id: "graph", label: "Knowledge Graph", icon: <Network className="h-3.5 w-3.5" /> },
  ];

  if (loading || !data) {
    return (
      <div className="p-6 flex items-center justify-center h-full">
        <div className="text-muted-foreground font-mono text-sm animate-pulse">Carregando memória...</div>
      </div>
    );
  }

  const filteredCognitive = data.cognitive_memory.filter(
    (m) =>
      m.text.toLowerCase().includes(search.toLowerCase()) ||
      m.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-4 md:p-6 h-full overflow-y-auto scrollbar-cyber">
      <div className="mb-6">
        <h1 className="text-2xl font-bold gradient-cyber-text">Explorador de Memória</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Memória de trabalho, cognitiva e grafo de conhecimento
          {!isApiConfigured() && <span className="ml-2 text-warning font-mono text-[10px]">• MOCK MODE</span>}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 flex-wrap">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all font-mono ${
              activeTab === tab.id
                ? "neon-border-cyan bg-primary/10 text-primary"
                : "glass text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Working Memory */}
      {activeTab === "working" && (
        <div className="grid gap-3">
          {data.working_memory.map((entry, i) => (
            <motion.div
              key={entry.chat_id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08 }}
              className="glass-card p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-3.5 w-3.5 text-primary" />
                  <span className="text-xs font-mono text-primary">chat_{entry.chat_id}</span>
                </div>
                <span className="text-[10px] font-mono text-muted-foreground">
                  {new Date(entry.updated_at).toLocaleString("pt-BR")}
                </span>
              </div>
              <p className="text-sm text-foreground">{entry.last_message}</p>
            </motion.div>
          ))}
        </div>
      )}

      {/* Cognitive Memory */}
      {activeTab === "cognitive" && (
        <div>
          <div className="glass-card flex items-center gap-2 px-3 py-2 mb-4 w-full max-w-md">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar memórias..."
              className="bg-transparent text-sm text-foreground placeholder-muted-foreground outline-none flex-1 font-mono"
            />
          </div>
          <div className="grid gap-3">
            {filteredCognitive.map((entry, i) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                className="glass-card p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono text-accent">{entry.id}</span>
                  <span className="text-[10px] font-mono text-muted-foreground">
                    {entry.user_id}
                  </span>
                </div>
                <p className="text-sm text-foreground">{entry.text}</p>
                <p className="text-[10px] font-mono text-muted-foreground/50 mt-2">
                  {new Date(entry.created_at).toLocaleDateString("pt-BR")}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Knowledge Graph stats */}
      {activeTab === "graph" && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-4"
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="glass-card p-5 text-center neon-border-cyan">
              <p className="text-3xl font-bold font-mono text-primary">{data.knowledge_graph.total_nodes.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground mt-1">Total Nodes</p>
            </div>
            <div className="glass-card p-5 text-center neon-border-violet">
              <p className="text-3xl font-bold font-mono text-accent">{data.knowledge_graph.total_edges.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground mt-1">Total Edges</p>
            </div>
            <div className="glass-card p-5 text-center">
              <p className="text-xl font-bold font-mono text-foreground">{data.knowledge_graph.last_ingestion}</p>
              <p className="text-xs text-muted-foreground mt-1">Last Ingestion</p>
            </div>
          </div>

          <div className="glass-card p-12 flex flex-col items-center justify-center text-center">
            <Network className="h-16 w-16 text-primary/30 mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-2">Visualização do Grafo</h3>
            <p className="text-sm text-muted-foreground max-w-md">
              Visualização interativa com nós clicáveis será conectada à API LightRAG.
            </p>
          </div>
        </motion.div>
      )}
    </div>
  );
}
