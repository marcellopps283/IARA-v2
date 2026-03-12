import { useState, useRef, useEffect, useCallback } from "react";
import { Pause, Play, Search, Copy, Trash2, Filter } from "lucide-react";
import { connectLogsWS, isApiConfigured } from "@/lib/api-client";
import { generateMockLog } from "@/lib/mock-data";
import type { LogEntry } from "@/lib/types";
import { toast } from "sonner";

const levelColors: Record<string, string> = {
  INFO: "text-primary",
  WARNING: "text-warning",
  ERROR: "text-destructive",
  CRITICAL: "text-destructive",
  DEBUG: "text-muted-foreground",
};

const levelBg: Record<string, string> = {
  INFO: "bg-primary/10",
  WARNING: "bg-warning/10",
  ERROR: "bg-destructive/10",
  CRITICAL: "bg-destructive/15",
  DEBUG: "bg-muted/30",
};

const ALL_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;

export default function TerminalPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const [search, setSearch] = useState("");
  const [levelFilter, setLevelFilter] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const autoScroll = useRef(true);
  const pausedRef = useRef(false);
  const bufferRef = useRef<LogEntry[]>([]);

  pausedRef.current = paused;

  // Connect to real WS or generate mock logs
  useEffect(() => {
    if (isApiConfigured()) {
      const ws = connectLogsWS((log) => {
        if (pausedRef.current) {
          bufferRef.current.push(log);
          return;
        }
        setLogs((prev) => [...prev.slice(-500), log]);
      });
      return () => ws.close();
    } else {
      // Mock mode: generate logs periodically
      // Initial batch
      setLogs(Array.from({ length: 30 }, () => generateMockLog()));
      const interval = setInterval(() => {
        if (pausedRef.current) return;
        setLogs((prev) => [...prev.slice(-500), generateMockLog()]);
      }, 600 + Math.random() * 1400);
      return () => clearInterval(interval);
    }
  }, []);

  // Flush buffer when unpaused
  useEffect(() => {
    if (!paused && bufferRef.current.length > 0) {
      setLogs((prev) => [...prev, ...bufferRef.current].slice(-500));
      bufferRef.current = [];
    }
  }, [paused]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    autoScroll.current = scrollHeight - scrollTop - clientHeight < 50;
  }, []);

  const copyLine = (log: LogEntry) => {
    navigator.clipboard.writeText(`[${log.timestamp}] [${log.level}] [${log.module}] ${log.message}`);
    toast.success("Linha copiada", { duration: 1500 });
  };

  const filteredLogs = logs.filter((log) => {
    if (levelFilter && log.level !== levelFilter) return false;
    if (search && !log.message.toLowerCase().includes(search.toLowerCase()) && !log.module.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="border-b border-border p-3 flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-1 glass-card px-2 py-1">
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar logs..."
            className="bg-transparent text-xs text-foreground placeholder-muted-foreground outline-none w-40 font-mono"
          />
        </div>

        <div className="flex gap-1">
          {ALL_LEVELS.map((lvl) => (
            <button
              key={lvl}
              onClick={() => setLevelFilter(levelFilter === lvl ? null : lvl)}
              className={`px-2 py-1 text-[10px] font-mono rounded transition-all ${
                levelFilter === lvl
                  ? `${levelBg[lvl]} ${levelColors[lvl]} neon-border-cyan`
                  : "glass text-muted-foreground hover:text-foreground"
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>

        <div className="flex-1" />

        <button
          onClick={() => setPaused(!paused)}
          className="flex items-center gap-1.5 glass-card px-3 py-1.5 text-xs font-mono text-muted-foreground hover:text-foreground transition-colors"
        >
          {paused ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
          {paused ? "Retomar" : "Pausar"}
        </button>

        <button
          onClick={() => setLogs([])}
          className="flex items-center gap-1.5 glass-card px-3 py-1.5 text-xs font-mono text-muted-foreground hover:text-destructive transition-colors"
        >
          <Trash2 className="h-3 w-3" />
          Limpar
        </button>

        <div className="text-[10px] font-mono text-muted-foreground">
          {filteredLogs.length} linhas
        </div>
      </div>

      {/* Log viewer */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto scrollbar-cyber font-mono text-xs"
      >
        {filteredLogs.map((log, i) => (
          <div
            key={`${log.timestamp}-${i}`}
            className="terminal-line group flex items-start gap-2 border-b border-border/30"
            onClick={() => copyLine(log)}
          >
            <span className="text-muted-foreground/50 shrink-0 w-20">
              {new Date(log.timestamp).toLocaleTimeString("pt-BR", { hour12: false })}
            </span>
            <span className={`shrink-0 w-16 font-semibold ${levelColors[log.level]}`}>
              {log.level}
            </span>
            <span className="text-accent/60 shrink-0 w-36 truncate">{log.module}</span>
            <span className="text-foreground flex-1">{log.message}</span>
            <Copy className="h-3 w-3 text-muted-foreground/0 group-hover:text-muted-foreground/60 shrink-0 transition-colors cursor-pointer" />
          </div>
        ))}
      </div>

      {/* Status bar */}
      <div className="border-t border-border px-3 py-1.5 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
        <span className="flex items-center gap-2">
          <Filter className="h-3 w-3" />
          {levelFilter ? `Filtro: ${levelFilter}` : "Sem filtro"}
          {search && ` • Busca: "${search}"`}
        </span>
        <span className="flex items-center gap-2">
          {!isApiConfigured() && <span className="text-warning">MOCK</span>}
          <div className={`w-1.5 h-1.5 rounded-full ${paused ? "bg-warning" : "bg-success animate-pulse-glow"}`} />
          {paused ? `Pausado (${bufferRef.current.length} buffered)` : "Streaming"}
        </span>
      </div>
    </div>
  );
}
