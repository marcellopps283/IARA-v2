import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { mockLatencyData, mockSuccessRateData } from "@/lib/mock-data";
import { isApiConfigured } from "@/lib/api-client";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Cpu, MemoryStick } from "lucide-react";

// ── Generate mock VPS resource history (last 30 minutes) ──
function generateResourceHistory() {
  const now = Date.now();
  return Array.from({ length: 30 }, (_, i) => {
    const time = new Date(now - (29 - i) * 60000);
    const baseCpu = 30 + Math.sin(i * 0.3) * 15;
    const baseRam = 55 + Math.sin(i * 0.2 + 1) * 12;
    return {
      time: time.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", hour12: false }),
      cpu: Math.max(5, Math.min(98, Math.round(baseCpu + (Math.random() - 0.5) * 20))),
      ram: Math.max(20, Math.min(98, Math.round(baseRam + (Math.random() - 0.5) * 15))),
    };
  });
}

const tooltipStyle = {
  background: "hsl(0, 0%, 7%)",
  border: "1px solid hsl(0, 0%, 14%)",
  borderRadius: "8px",
  fontSize: "12px",
  fontFamily: "JetBrains Mono",
};

export default function MetricsPage() {
  const [vpsHistory, setVpsHistory] = useState(generateResourceHistory);

  // Simulate live updates every 10s
  useEffect(() => {
    const interval = setInterval(() => {
      setVpsHistory((prev) => {
        const last = prev[prev.length - 1];
        const now = new Date();
        const newPoint = {
          time: now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", hour12: false }),
          cpu: Math.max(5, Math.min(98, last.cpu + Math.round((Math.random() - 0.5) * 10))),
          ram: Math.max(20, Math.min(98, last.ram + Math.round((Math.random() - 0.5) * 6))),
        };
        return [...prev.slice(1), newPoint];
      });
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const avgCpu = Math.round(vpsHistory.reduce((a, d) => a + d.cpu, 0) / vpsHistory.length);
  const avgRam = Math.round(vpsHistory.reduce((a, d) => a + d.ram, 0) / vpsHistory.length);
  const maxCpu = Math.max(...vpsHistory.map((d) => d.cpu));
  const maxRam = Math.max(...vpsHistory.map((d) => d.ram));

  return (
    <div className="p-4 md:p-6 h-full overflow-y-auto scrollbar-cyber pt-12 md:pt-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold gradient-cyber-text">Métricas</h1>
        <p className="text-sm text-muted-foreground mt-1">
          LLM, Swarm/Council e recursos da VPS
          {!isApiConfigured() && <span className="ml-2 text-warning font-mono text-[10px]">• MOCK MODE</span>}
        </p>
      </div>

      <div className="grid gap-6">
        {/* ── VPS Resource History ──────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* CPU Chart */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-primary" />
                <div>
                  <h3 className="text-sm font-semibold text-foreground">CPU</h3>
                  <p className="text-[10px] text-muted-foreground">Últimos 30 minutos</p>
                </div>
              </div>
              <div className="text-right">
                <span className={`text-2xl font-bold font-mono ${avgCpu > 80 ? "text-destructive" : avgCpu > 60 ? "text-warning" : "text-primary"}`}>
                  {avgCpu}%
                </span>
                <p className="text-[10px] text-muted-foreground">avg • max {maxCpu}%</p>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={vpsHistory}>
                <defs>
                  <linearGradient id="cpuGradNormal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(185, 100%, 50%)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(185, 100%, 50%)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="cpuGradWarn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(38, 92%, 50%)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(38, 92%, 50%)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="cpuGradDanger" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(0, 72%, 51%)" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="hsl(0, 72%, 51%)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(0, 0%, 14%)" />
                <XAxis dataKey="time" stroke="hsl(0, 0%, 35%)" fontSize={9} fontFamily="JetBrains Mono" interval="preserveStartEnd" />
                <YAxis stroke="hsl(0, 0%, 35%)" fontSize={9} fontFamily="JetBrains Mono" domain={[0, 100]} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "hsl(0, 0%, 55%)" }} />
                <Area
                  type="monotone"
                  dataKey="cpu"
                  stroke={maxCpu > 80 ? "hsl(0, 72%, 51%)" : avgCpu > 60 ? "hsl(38, 92%, 50%)" : "hsl(185, 100%, 50%)"}
                  fill={maxCpu > 80 ? "url(#cpuGradDanger)" : avgCpu > 60 ? "url(#cpuGradWarn)" : "url(#cpuGradNormal)"}
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </motion.div>

          {/* RAM Chart */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <MemoryStick className="h-4 w-4 text-accent" />
                <div>
                  <h3 className="text-sm font-semibold text-foreground">RAM</h3>
                  <p className="text-[10px] text-muted-foreground">Últimos 30 minutos</p>
                </div>
              </div>
              <div className="text-right">
                <span className={`text-2xl font-bold font-mono ${avgRam > 80 ? "text-destructive" : avgRam > 60 ? "text-warning" : "text-accent"}`}>
                  {avgRam}%
                </span>
                <p className="text-[10px] text-muted-foreground">avg • max {maxRam}%</p>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={vpsHistory}>
                <defs>
                  <linearGradient id="ramGradNormal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(263, 70%, 58%)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(263, 70%, 58%)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="ramGradWarn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(38, 92%, 50%)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(38, 92%, 50%)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="ramGradDanger" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(0, 72%, 51%)" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="hsl(0, 72%, 51%)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(0, 0%, 14%)" />
                <XAxis dataKey="time" stroke="hsl(0, 0%, 35%)" fontSize={9} fontFamily="JetBrains Mono" interval="preserveStartEnd" />
                <YAxis stroke="hsl(0, 0%, 35%)" fontSize={9} fontFamily="JetBrains Mono" domain={[0, 100]} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "hsl(0, 0%, 55%)" }} />
                <Area
                  type="monotone"
                  dataKey="ram"
                  stroke={maxRam > 80 ? "hsl(0, 72%, 51%)" : avgRam > 60 ? "hsl(38, 92%, 50%)" : "hsl(263, 70%, 58%)"}
                  fill={maxRam > 80 ? "url(#ramGradDanger)" : avgRam > 60 ? "url(#ramGradWarn)" : "url(#ramGradNormal)"}
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </motion.div>
        </div>

        {/* ── LLM Latency ──────────────────────────── */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Latência LLM</h3>
              <p className="text-xs text-muted-foreground">Últimas 24 horas (ms)</p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-bold font-mono text-primary">
                {Math.round(mockLatencyData.reduce((a, d) => a + d.value, 0) / mockLatencyData.length)}
              </span>
              <span className="text-xs text-muted-foreground ml-1">ms avg</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={mockLatencyData}>
              <defs>
                <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(185, 100%, 50%)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(185, 100%, 50%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(0, 0%, 14%)" />
              <XAxis dataKey="timestamp" stroke="hsl(0, 0%, 35%)" fontSize={10} fontFamily="JetBrains Mono" />
              <YAxis stroke="hsl(0, 0%, 35%)" fontSize={10} fontFamily="JetBrains Mono" />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "hsl(0, 0%, 55%)" }} itemStyle={{ color: "hsl(185, 100%, 50%)" }} />
              <Area type="monotone" dataKey="value" stroke="hsl(185, 100%, 50%)" fill="url(#cyanGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* ── Swarm/Council Success Rate ────────────── */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Taxa de Sucesso Swarm/Council</h3>
              <p className="text-xs text-muted-foreground">Últimas 24 horas (%)</p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-bold font-mono text-accent">
                {Math.round(mockSuccessRateData.reduce((a, d) => a + d.value, 0) / mockSuccessRateData.length)}
              </span>
              <span className="text-xs text-muted-foreground ml-1">% avg</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={mockSuccessRateData}>
              <defs>
                <linearGradient id="violetGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(263, 70%, 58%)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(263, 70%, 58%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(0, 0%, 14%)" />
              <XAxis dataKey="timestamp" stroke="hsl(0, 0%, 35%)" fontSize={10} fontFamily="JetBrains Mono" />
              <YAxis stroke="hsl(0, 0%, 35%)" fontSize={10} fontFamily="JetBrains Mono" domain={[70, 100]} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "hsl(0, 0%, 55%)" }} itemStyle={{ color: "hsl(263, 70%, 58%)" }} />
              <Area type="monotone" dataKey="value" stroke="hsl(263, 70%, 58%)" fill="url(#violetGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>
      </div>
    </div>
  );
}
