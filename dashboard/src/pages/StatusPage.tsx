import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Activity, Clock, Gauge, Server, Cpu, Network, Users, Brain } from "lucide-react";
import { fetchStatus, isApiConfigured } from "@/lib/api-client";
import { mockStatusResponse } from "@/lib/mock-data";
import type { StatusResponse } from "@/lib/types";

type StatusColor = "online" | "degraded" | "offline";

function getStatusColor(status: string): StatusColor {
  const s = status.toLowerCase();
  if (["online", "ready", "idle"].includes(s)) return "online";
  if (["busy"].includes(s)) return "degraded";
  return "offline";
}

const statusConfig: Record<StatusColor, { dotClass: string; textClass: string }> = {
  online: { dotClass: "status-dot-online", textClass: "text-success" },
  degraded: { dotClass: "status-dot-degraded", textClass: "text-warning" },
  offline: { dotClass: "status-dot-offline", textClass: "text-destructive" },
};

// ── Live Activity mock data ─────────────────────────────
interface ActivityEvent {
  id: string;
  agent: string;
  action: string;
  timestamp: Date;
  active: boolean;
  icon: string;
}

const agentActivities = [
  { agent: "Researcher", actions: ["Buscando no Google Scholar...", "Consultando LightRAG...", "Sintetizando fontes..."], icon: "🔍" },
  { agent: "Coder", actions: ["Filtrando arquivos Python...", "Analisando pipeline ML...", "Gerando patch..."], icon: "💻" },
  { agent: "Analyst", actions: ["Calculando métricas Q4...", "Comparando benchmarks...", "Gerando relatório..."], icon: "📊" },
  { agent: "Council", actions: ["Debatendo consenso...", "Validando hipótese...", "Votação em andamento..."], icon: "🏛️" },
  { agent: "Swarm", actions: ["Orquestrando agentes...", "Distribuindo tarefas...", "Consolidando resultados..."], icon: "🐝" },
];

let activityId = 0;

function generateActivity(): ActivityEvent {
  const agent = agentActivities[Math.floor(Math.random() * agentActivities.length)];
  return {
    id: `act-${++activityId}`,
    agent: agent.agent,
    action: agent.actions[Math.floor(Math.random() * agent.actions.length)],
    timestamp: new Date(),
    active: Math.random() > 0.3,
    icon: agent.icon,
  };
}

export default function StatusPage() {
  const [data, setData] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activities, setActivities] = useState<ActivityEvent[]>(() =>
    Array.from({ length: 6 }, () => generateActivity())
  );

  useEffect(() => {
    async function load() {
      if (!isApiConfigured()) {
        setData(mockStatusResponse);
        setLoading(false);
        return;
      }
      try {
        const res = await fetchStatus();
        setData(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erro ao carregar status");
        setData(mockStatusResponse);
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  // Live activity feed
  useEffect(() => {
    const interval = setInterval(() => {
      setActivities((prev) => {
        const updated = prev.map((a) => ({ ...a, active: Math.random() > 0.5 }));
        const newActivity = generateActivity();
        return [newActivity, ...updated].slice(0, 8);
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  if (loading || !data) {
    return (
      <div className="p-6 flex items-center justify-center h-full">
        <div className="text-muted-foreground font-mono text-sm animate-pulse">Carregando status...</div>
      </div>
    );
  }

  const { system } = data;

  const services = [
    { name: "IARA Core", icon: <Server className="h-5 w-5" />, status: system.core.status, details: [{ label: "Uptime", value: system.core.uptime }, { label: "Versão", value: system.core.version }] },
    { name: "Redis", icon: <Gauge className="h-5 w-5" />, status: system.infrastructure.redis.status, details: [{ label: "Latência", value: `${system.infrastructure.redis.latency_ms}ms` }] },
    { name: "Qdrant", icon: <Activity className="h-5 w-5" />, status: system.infrastructure.qdrant.status, details: [{ label: "Collections", value: system.infrastructure.qdrant.collections.join(", ") }] },
    { name: "Infinity TEI", icon: <Clock className="h-5 w-5" />, status: system.infrastructure.infinity.status, details: [{ label: "Modelo", value: system.infrastructure.infinity.model }] },
  ];

  const agents = [
    { name: "Swarm", icon: <Users className="h-5 w-5" />, status: system.agents.swarm.status, details: [{ label: "Tarefas ativas", value: String(system.agents.swarm.active_tasks) }] },
    { name: "Council", icon: <Cpu className="h-5 w-5" />, status: system.agents.council.status, details: [] },
  ];

  return (
    <div className="p-4 md:p-6 overflow-y-auto h-full scrollbar-cyber pt-12 md:pt-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold gradient-cyber-text">Status dos Serviços</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Monitoramento em tempo real da infraestrutura IARA
          {!isApiConfigured() && <span className="ml-2 text-warning font-mono text-[10px]">• MOCK MODE</span>}
        </p>
        {error && <p className="text-xs text-destructive mt-1 font-mono">{error}</p>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: services + agents */}
        <div className="lg:col-span-2 space-y-6">
          {/* Infrastructure */}
          <div>
            <h2 className="text-xs uppercase tracking-widest text-muted-foreground mb-3 font-mono">Infraestrutura</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {services.map((svc, i) => {
                const color = getStatusColor(svc.status);
                const cfg = statusConfig[color];
                return (
                  <motion.div key={svc.name} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08, duration: 0.4 }}
                    className={`glass-card p-5 ${color === "online" ? "neon-border-cyan" : color === "degraded" ? "neon-border-violet" : "border-destructive/30"}`}>
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-primary">{svc.icon}</div>
                      <div className="flex items-center gap-2">
                        <div className={cfg.dotClass} />
                        <span className={`text-xs font-mono ${cfg.textClass}`}>{svc.status}</span>
                      </div>
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">{svc.name}</h3>
                    <div className="space-y-2 text-xs font-mono">
                      {svc.details.map((d) => (
                        <div key={d.label} className="flex justify-between">
                          <span className="text-muted-foreground">{d.label}</span>
                          <span className="text-foreground">{d.value}</span>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>

          {/* Agents */}
          <div>
            <h2 className="text-xs uppercase tracking-widest text-muted-foreground mb-3 font-mono">Agentes</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {agents.map((agent, i) => {
                const color = getStatusColor(agent.status);
                const cfg = statusConfig[color];
                return (
                  <motion.div key={agent.name} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 + i * 0.08, duration: 0.4 }}
                    className={`glass-card p-5 ${color === "online" ? "neon-border-cyan" : color === "degraded" ? "neon-border-violet" : "border-destructive/30"}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="text-accent">{agent.icon}</div>
                        <h3 className="text-base font-semibold text-foreground">{agent.name}</h3>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className={cfg.dotClass} />
                        <span className={`text-xs font-mono ${cfg.textClass}`}>{agent.status}</span>
                      </div>
                    </div>
                    {agent.details.map((d) => (
                      <div key={d.label} className="flex justify-between text-xs font-mono">
                        <span className="text-muted-foreground">{d.label}</span>
                        <span className="text-foreground">{d.value}</span>
                      </div>
                    ))}
                  </motion.div>
                );
              })}
            </div>
          </div>

          {/* Memory Metrics */}
          <div>
            <h2 className="text-xs uppercase tracking-widest text-muted-foreground mb-3 font-mono">Memória</h2>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
              className="glass-card p-4 flex flex-wrap gap-6 items-center text-xs font-mono">
              <div className="flex items-center gap-3">
                <Brain className="h-4 w-4 text-primary" />
                <div>
                  <span className="text-muted-foreground">Core Facts</span>
                  <span className="ml-2 text-foreground font-semibold">{system.memory_metrics.core_facts_count}</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Network className="h-4 w-4 text-accent" />
                <div>
                  <span className="text-muted-foreground">Graph Nodes</span>
                  <span className="ml-2 text-foreground font-semibold">{system.memory_metrics.graph_nodes}</span>
                </div>
              </div>
            </motion.div>
          </div>
        </div>

        {/* Right column: Live Activity */}
        <div>
          <h2 className="text-xs uppercase tracking-widest text-muted-foreground mb-3 font-mono">Live Activity</h2>
          <div className="glass-card p-4 space-y-0">
            {activities.map((event, i) => (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="flex items-start gap-3 py-3 relative"
              >
                {/* Timeline line */}
                {i < activities.length - 1 && (
                  <div className="absolute left-[14px] top-[36px] bottom-0 w-px bg-border/50" />
                )}

                {/* Dot with ping */}
                <div className="relative shrink-0 mt-0.5">
                  <div className={`w-[10px] h-[10px] rounded-full ${
                    event.active ? "bg-success" : "bg-muted-foreground/30"
                  }`} />
                  {event.active && (
                    <div className="absolute inset-0 w-[10px] h-[10px] rounded-full bg-success animate-ping opacity-40" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="text-sm">{event.icon}</span>
                    <span className="text-xs font-semibold text-foreground">{event.agent}</span>
                    {event.active && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-success/10 text-success font-mono">ATIVO</span>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground truncate">{event.action}</p>
                  <p className="text-[9px] font-mono text-muted-foreground/50 mt-0.5">
                    {event.timestamp.toLocaleTimeString("pt-BR", { hour12: false })}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
