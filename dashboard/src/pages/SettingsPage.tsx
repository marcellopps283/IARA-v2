import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  Key,
  Thermometer,
  RotateCcw,
  BookOpen,
  Trash2,
  Server,
  Cpu,
  MemoryStick,
  RefreshCw,
  Bug,
  Info,
  Eye,
  EyeOff,
  Save,
  Loader2,
} from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import {
  isApiConfigured,
  patchSettings,
  saveApiKeys as saveApiKeysApi,
  resetWorkingMemory,
  forceReindex,
  deleteFact as deleteFactApi,
  fetchFacts,
  restartContainer,
} from "@/lib/api-client";

// Mock data fallback
const mockFacts = [
  { id: "f1", text: "Nome do usuário: Lucas", source: "mem0", created: "2025-03-10" },
  { id: "f2", text: "Linguagem preferida: Python", source: "mem0", created: "2025-03-09" },
  { id: "f3", text: "Projeto atual: IARA v2", source: "mem0", created: "2025-03-08" },
  { id: "f4", text: "Prefere respostas em português", source: "mem0", created: "2025-03-07" },
  { id: "f5", text: "Stack: FastAPI + React + Qdrant", source: "mem0", created: "2025-03-06" },
];

const llmProviders = [
  { id: "groq", name: "Groq", models: ["llama-3.3-70b", "mixtral-8x7b", "gemma2-9b"] },
  { id: "gemini", name: "Gemini", models: ["gemini-2.5-pro", "gemini-2.5-flash"] },
  { id: "openrouter", name: "OpenRouter", models: ["anthropic/claude-3.5", "meta/llama-3.1-405b"] },
];

export default function SettingsPage() {
  const apiReady = isApiConfigured();

  // LLM state
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    groq: "",
    gemini: "",
    openrouter: "",
  });
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [primaryModel, setPrimaryModel] = useState("groq/llama-3.3-70b");
  const [backupModel, setBackupModel] = useState("gemini/gemini-2.5-flash");
  const [temperature, setTemperature] = useState([0.7]);

  // Memory state
  const [facts, setFacts] = useState(mockFacts);

  // VPS state
  const [debugLogs, setDebugLogs] = useState(false);

  // Loading states
  const [savingKeys, setSavingKeys] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [restarting, setRestarting] = useState(false);

  // Mock VPS metrics
  const cpuUsage = 34;
  const ramUsage = 61;
  const ramTotal = "4GB";

  // Load facts from API
  useEffect(() => {
    if (!apiReady) return;
    fetchFacts()
      .then(setFacts)
      .catch(() => setFacts(mockFacts));
  }, [apiReady]);

  // ── Handlers ──────────────────────────────────────────

  const handleSaveKeys = async () => {
    setSavingKeys(true);
    try {
      if (apiReady) await saveApiKeysApi(apiKeys);
      toast.success("API Keys salvas com sucesso");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao salvar keys");
    } finally {
      setSavingKeys(false);
    }
  };

  const handleModelChange = async (field: "active_model" | "backup_model", value: string) => {
    if (field === "active_model") setPrimaryModel(value);
    else setBackupModel(value);
    try {
      if (apiReady) await patchSettings({ [field]: value });
      toast.success(`Modelo ${field === "active_model" ? "titular" : "reserva"} atualizado`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao atualizar modelo");
    }
  };

  const handleTemperatureCommit = async (val: number[]) => {
    setTemperature(val);
    try {
      if (apiReady) await patchSettings({ temperature: val[0] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao atualizar temperatura");
    }
  };

  const handleResetWorkingMemory = async () => {
    setResetting(true);
    try {
      if (apiReady) await resetWorkingMemory();
      toast.success("Memória de curto prazo limpa");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao resetar memória");
    } finally {
      setResetting(false);
    }
  };

  const handleForceIndex = async () => {
    setIndexing(true);
    try {
      if (apiReady) await forceReindex();
      toast.success("Indexação concluída");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro na indexação");
    } finally {
      setIndexing(false);
    }
  };

  const handleDeleteFact = async (id: string) => {
    try {
      if (apiReady) await deleteFactApi(id);
      setFacts((prev) => prev.filter((f) => f.id !== id));
      toast.success("Fato removido do Mem0");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao remover fato");
    }
  };

  const handleRestartContainer = async () => {
    setRestarting(true);
    try {
      if (apiReady) await restartContainer();
      toast.success("Container reiniciado com sucesso");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao reiniciar container");
    } finally {
      setRestarting(false);
    }
  };

  const handleLogLevelToggle = async (checked: boolean) => {
    setDebugLogs(checked);
    try {
      if (apiReady) await patchSettings({ log_level: checked ? "DEBUG" : "INFO" });
      toast.success(`Logs alterados para ${checked ? "Debug" : "Info"}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao alterar nível de logs");
    }
  };

  const sectionDelay = 0.1;

  return (
    <div className="p-4 md:p-6 h-full overflow-y-auto scrollbar-cyber">
      <div className="mb-6 pt-10 md:pt-0">
        <h1 className="text-2xl font-bold gradient-cyber-text">Configurações</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Gestão de LLMs, memória e infraestrutura
          {!apiReady && <span className="ml-2 text-warning font-mono text-[10px]">• MOCK MODE</span>}
        </p>
      </div>

      <div className="space-y-8 max-w-3xl">
        {/* ═══════════════════════════════════════════════ */}
        {/* 1. GESTÃO DE CÉREBRO (LLMs) */}
        {/* ═══════════════════════════════════════════════ */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: sectionDelay * 0 }}
        >
          <div className="flex items-center gap-2 mb-4">
            <Brain className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">Gestão de Cérebro</h2>
          </div>

          {/* API Keys */}
          <div className="glass-card p-5 mb-4">
            <div className="flex items-center gap-2 mb-4">
              <Key className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-medium text-foreground">API Keys</h3>
            </div>
            <div className="space-y-3">
              {llmProviders.map((provider) => (
                <div key={provider.id} className="flex items-center gap-3">
                  <label className="text-xs font-mono text-muted-foreground w-24 shrink-0">
                    {provider.name}
                  </label>
                  <div className="flex-1 relative">
                    <input
                      type={showKeys[provider.id] ? "text" : "password"}
                      value={apiKeys[provider.id]}
                      onChange={(e) =>
                        setApiKeys((prev) => ({ ...prev, [provider.id]: e.target.value }))
                      }
                      placeholder={`${provider.name} API Key...`}
                      className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-xs font-mono text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-primary/50 transition-colors"
                    />
                    <button
                      onClick={() =>
                        setShowKeys((prev) => ({ ...prev, [provider.id]: !prev[provider.id] }))
                      }
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showKeys[provider.id] ? (
                        <EyeOff className="h-3.5 w-3.5" />
                      ) : (
                        <Eye className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <button
              onClick={handleSaveKeys}
              disabled={savingKeys}
              className="mt-4 flex items-center gap-2 px-4 py-2 rounded-lg gradient-cyber text-primary-foreground text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {savingKeys ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Salvar Keys
            </button>
          </div>

          {/* Model Selection */}
          <div className="glass-card p-5 mb-4">
            <h3 className="text-sm font-medium text-foreground mb-4">Seleção de Modelo</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted-foreground mb-2 block">Modelo Titular</label>
                <select
                  value={primaryModel}
                  onChange={(e) => handleModelChange("active_model", e.target.value)}
                  className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-xs font-mono text-foreground outline-none focus:border-primary/50 transition-colors"
                >
                  {llmProviders.map((p) =>
                    p.models.map((m) => (
                      <option key={`${p.id}-${m}`} value={`${p.id}/${m}`}>
                        {p.name} / {m}
                      </option>
                    ))
                  )}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-2 block">Modelo Reserva</label>
                <select
                  value={backupModel}
                  onChange={(e) => handleModelChange("backup_model", e.target.value)}
                  className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-xs font-mono text-foreground outline-none focus:border-primary/50 transition-colors"
                >
                  {llmProviders.map((p) =>
                    p.models.map((m) => (
                      <option key={`${p.id}-${m}`} value={`${p.id}/${m}`}>
                        {p.name} / {m}
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>
          </div>

          {/* Temperature */}
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Thermometer className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-medium text-foreground">Temperatura</h3>
              <span className="ml-auto text-lg font-bold font-mono text-primary">
                {temperature[0].toFixed(2)}
              </span>
            </div>
            <Slider
              value={temperature}
              onValueChange={setTemperature}
              onValueCommit={handleTemperatureCommit}
              min={0}
              max={2}
              step={0.05}
              className="my-3"
            />
            <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
              <span>🎯 Precisa (0.0)</span>
              <span>⚖️ Balanceada (0.7)</span>
              <span>🎨 Criativa (2.0)</span>
            </div>
          </div>
        </motion.section>

        {/* ═══════════════════════════════════════════════ */}
        {/* 2. MANUTENÇÃO DE MEMÓRIA */}
        {/* ═══════════════════════════════════════════════ */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: sectionDelay * 1 }}
        >
          <div className="flex items-center gap-2 mb-4">
            <RotateCcw className="h-5 w-5 text-accent" />
            <h2 className="text-lg font-semibold text-foreground">Manutenção de Memória</h2>
          </div>

          {/* Action buttons */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <button
              onClick={handleResetWorkingMemory}
              disabled={resetting}
              className="glass-card p-4 flex items-center gap-3 hover:bg-muted/30 transition-colors group text-left disabled:opacity-50"
            >
              <div className="w-10 h-10 rounded-lg bg-destructive/10 flex items-center justify-center shrink-0 group-hover:bg-destructive/20 transition-colors">
                {resetting ? <Loader2 className="h-5 w-5 text-destructive animate-spin" /> : <RotateCcw className="h-5 w-5 text-destructive" />}
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">Reset Memória Curta</p>
                <p className="text-[11px] text-muted-foreground">Limpa a working memory atual</p>
              </div>
            </button>

            <button
              onClick={handleForceIndex}
              disabled={indexing}
              className="glass-card p-4 flex items-center gap-3 hover:bg-muted/30 transition-colors group text-left disabled:opacity-50"
            >
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
                {indexing ? <Loader2 className="h-5 w-5 text-primary animate-spin" /> : <BookOpen className="h-5 w-5 text-primary" />}
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">Forçar Indexação</p>
                <p className="text-[11px] text-muted-foreground">Re-indexar documentos no LightRAG</p>
              </div>
            </button>
          </div>

          {/* Facts viewer */}
          <div className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-foreground">Fatos Salvos (Mem0)</h3>
              <span className="text-xs font-mono text-muted-foreground">{facts.length} fatos</span>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-cyber">
              {facts.map((fact) => (
                <div
                  key={fact.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-muted/20 hover:bg-muted/40 transition-colors group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-foreground">{fact.text}</p>
                    <p className="text-[10px] font-mono text-muted-foreground mt-1">
                      {fact.source} • {fact.created}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDeleteFact(fact.id)}
                    className="shrink-0 p-1.5 rounded-md text-muted-foreground/0 group-hover:text-destructive hover:bg-destructive/10 transition-all"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {facts.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-4">Nenhum fato salvo</p>
              )}
            </div>
          </div>
        </motion.section>

        {/* ═══════════════════════════════════════════════ */}
        {/* 3. MONITORAMENTO DA VPS */}
        {/* ═══════════════════════════════════════════════ */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: sectionDelay * 2 }}
          className="pb-8"
        >
          <div className="flex items-center gap-2 mb-4">
            <Server className="h-5 w-5 text-success" />
            <h2 className="text-lg font-semibold text-foreground">Monitoramento VPS</h2>
          </div>

          {/* Resource usage */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div className="glass-card p-5">
              <div className="flex items-center gap-2 mb-3">
                <Cpu className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium text-foreground">CPU</span>
                <span className="ml-auto text-lg font-bold font-mono text-primary">{cpuUsage}%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${cpuUsage}%`,
                    background: cpuUsage > 80 ? "hsl(var(--destructive))" : cpuUsage > 60 ? "hsl(var(--warning))" : "hsl(var(--primary))",
                  }}
                />
              </div>
            </div>

            <div className="glass-card p-5">
              <div className="flex items-center gap-2 mb-3">
                <MemoryStick className="h-4 w-4 text-accent" />
                <span className="text-sm font-medium text-foreground">RAM</span>
                <span className="ml-auto text-lg font-bold font-mono text-accent">
                  {ramUsage}%
                  <span className="text-xs text-muted-foreground ml-1 font-normal">/ {ramTotal}</span>
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${ramUsage}%`,
                    background: ramUsage > 80 ? "hsl(var(--destructive))" : ramUsage > 60 ? "hsl(var(--warning))" : "hsl(var(--accent))",
                  }}
                />
              </div>
            </div>
          </div>

          {/* Actions row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button
              onClick={handleRestartContainer}
              disabled={restarting}
              className="glass-card p-4 flex items-center gap-3 hover:bg-muted/30 transition-colors group text-left disabled:opacity-50"
            >
              <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center shrink-0 group-hover:bg-warning/20 transition-colors">
                {restarting ? <Loader2 className="h-5 w-5 text-warning animate-spin" /> : <RefreshCw className="h-5 w-5 text-warning" />}
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">Restart Container</p>
                <p className="text-[11px] text-muted-foreground">Reinicia apenas o container IARA</p>
              </div>
            </button>

            <div className="glass-card p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-muted/30 flex items-center justify-center shrink-0">
                {debugLogs ? (
                  <Bug className="h-5 w-5 text-warning" />
                ) : (
                  <Info className="h-5 w-5 text-primary" />
                )}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">Nível de Logs</p>
                <p className="text-[11px] text-muted-foreground">
                  {debugLogs ? "Debug (verbose)" : "Info (resumido)"}
                </p>
              </div>
              <Switch checked={debugLogs} onCheckedChange={handleLogLevelToggle} />
            </div>
          </div>
        </motion.section>
      </div>
    </div>
  );
}
