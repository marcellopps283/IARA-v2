import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { FlaskConical, Send, Loader2, Clock, Zap } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { getMockResponse } from "@/lib/mock-data";

interface ModelResult {
  content: string;
  tokensPerSec: number;
  responseTime: number;
  done: boolean;
}

const availableModels = [
  { id: "groq/llama-3.3-70b", name: "Groq / LLaMA 3.3 70B" },
  { id: "groq/mixtral-8x7b", name: "Groq / Mixtral 8x7B" },
  { id: "gemini/gemini-2.5-pro", name: "Gemini 2.5 Pro" },
  { id: "gemini/gemini-2.5-flash", name: "Gemini 2.5 Flash" },
  { id: "openrouter/claude-3.5", name: "Claude 3.5 Sonnet" },
];

export default function PlaygroundPage() {
  const [prompt, setPrompt] = useState("");
  const [modelA, setModelA] = useState(availableModels[0].id);
  const [modelB, setModelB] = useState(availableModels[3].id);
  const [resultA, setResultA] = useState<ModelResult | null>(null);
  const [resultB, setResultB] = useState<ModelResult | null>(null);
  const [running, setRunning] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + "px";
    }
  }, [prompt]);

  const simulateResponse = async (
    setter: React.Dispatch<React.SetStateAction<ModelResult | null>>,
    speed: number
  ) => {
    const response = getMockResponse();
    const words = response.split(" ");
    const startTime = Date.now();
    let accumulated = "";

    setter({ content: "", tokensPerSec: 0, responseTime: 0, done: false });

    for (let i = 0; i < words.length; i++) {
      accumulated += (i > 0 ? " " : "") + words[i];
      const elapsed = (Date.now() - startTime) / 1000;
      setter({
        content: accumulated,
        tokensPerSec: Math.round((i + 1) / Math.max(elapsed, 0.1)),
        responseTime: Math.round(elapsed * 1000),
        done: false,
      });
      await new Promise((r) => setTimeout(r, speed + Math.random() * speed * 0.5));
    }

    const finalTime = (Date.now() - startTime) / 1000;
    setter((prev) => prev ? { ...prev, done: true, tokensPerSec: Math.round(words.length / finalTime), responseTime: Math.round(finalTime * 1000) } : prev);
  };

  const handleRun = async () => {
    if (!prompt.trim() || running) return;
    setRunning(true);
    setResultA(null);
    setResultB(null);

    await Promise.all([
      simulateResponse(setResultA, 25),
      simulateResponse(setResultB, 40),
    ]);

    setRunning(false);
  };

  const ModelName = (id: string) => availableModels.find((m) => m.id === id)?.name || id;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 md:p-6 pb-3 pt-12 md:pt-6">
        <h1 className="text-2xl font-bold gradient-cyber-text">Playground</h1>
        <p className="text-sm text-muted-foreground mt-1">Compare modelos lado a lado</p>
      </div>

      {/* Prompt input */}
      <div className="px-4 md:px-6 pb-4">
        <div className="glass-card p-4">
          <div className="flex flex-col md:flex-row gap-3 mb-3">
            <div className="flex-1">
              <label className="text-[10px] font-mono text-muted-foreground mb-1 block">Modelo A</label>
              <select
                value={modelA}
                onChange={(e) => setModelA(e.target.value)}
                className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-xs font-mono text-foreground outline-none focus:border-primary/50"
              >
                {availableModels.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="text-[10px] font-mono text-muted-foreground mb-1 block">Modelo B</label>
              <select
                value={modelB}
                onChange={(e) => setModelB(e.target.value)}
                className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-xs font-mono text-foreground outline-none focus:border-primary/50"
              >
                {availableModels.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleRun(); } }}
              placeholder="Digite seu prompt para comparar..."
              rows={1}
              className="flex-1 bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder-muted-foreground resize-none outline-none focus:border-primary/50 max-h-[120px]"
            />
            <button
              onClick={handleRun}
              disabled={!prompt.trim() || running}
              className="shrink-0 w-10 h-10 rounded-lg flex items-center justify-center gradient-cyber text-primary-foreground disabled:opacity-30 transition-all"
            >
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>

      {/* Results side by side */}
      <div className="flex-1 px-4 md:px-6 pb-4 overflow-hidden">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
          {[{ result: resultA, model: modelA, label: "A", color: "primary" }, { result: resultB, model: modelB, label: "B", color: "accent" }].map(({ result, model, label, color }) => (
            <div key={label} className="glass-card flex flex-col overflow-hidden">
              {/* Model header */}
              <div className={`px-4 py-2.5 border-b border-border/30 flex items-center justify-between`}>
                <div className="flex items-center gap-2">
                  <div className={`w-5 h-5 rounded-md bg-${color}/20 flex items-center justify-center`}>
                    <FlaskConical className={`h-3 w-3 text-${color}`} />
                  </div>
                  <span className="text-xs font-medium text-foreground truncate">{ModelName(model)}</span>
                </div>
                {result && (
                  <div className="flex items-center gap-3 text-[10px] font-mono text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {result.responseTime}ms
                    </span>
                    <span className="flex items-center gap-1">
                      <Zap className="h-3 w-3" />
                      {result.tokensPerSec} t/s
                    </span>
                  </div>
                )}
              </div>

              {/* Response content */}
              <div className="flex-1 overflow-y-auto scrollbar-cyber p-4">
                {result ? (
                  <div className="prose prose-sm prose-invert max-w-none
                    [&_pre]:bg-muted [&_pre]:rounded-xl [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-xs [&_pre]:border [&_pre]:border-border/50
                    [&_code]:text-primary [&_code]:font-mono [&_code]:text-xs [&_code]:bg-muted/60 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded-md
                    [&_pre_code]:bg-transparent [&_pre_code]:p-0
                    [&_strong]:text-foreground [&_p]:text-foreground/90 [&_li]:text-foreground/90">
                    <ReactMarkdown>{result.content}</ReactMarkdown>
                    {!result.done && (
                      <span className="inline-block w-2 h-4 bg-foreground/50 animate-pulse ml-0.5" />
                    )}
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-muted-foreground/40">
                    <p className="text-sm">Modelo {label}</p>
                  </div>
                )}
              </div>

              {/* Metrics bar */}
              {result?.done && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="px-4 py-2 border-t border-border/30 flex items-center gap-4"
                >
                  <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: "100%" }}
                      transition={{ duration: 0.5 }}
                      className={`h-full rounded-full bg-${color}`}
                    />
                  </div>
                  <span className="text-[10px] font-mono text-muted-foreground">✓ Concluído</span>
                </motion.div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
