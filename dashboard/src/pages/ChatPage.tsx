import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Loader2,
  Plus,
  Sparkles,
  Copy,
  Share2,
  ChevronDown,
  Image as ImageIcon,
  Paperclip,
  Globe,
  X,
  Check,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { createChatMessage, getMockResponse } from "@/lib/mock-data";
import type { ChatMessage, ReasoningMode } from "@/lib/types";
import { isApiConfigured, patchSettings } from "@/lib/api-client";
import { toast } from "sonner";

// ── Reasoning icon component ──────────────────────────
function ReasoningIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}>
      <path d="M8 1v4M8 11v4M1 8h4M11 8h4M3.5 3.5l2.5 2.5M10 10l2.5 2.5M12.5 3.5L10 6M6 10l-2.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [reasoningMode, setReasoningMode] = useState<ReasoningMode>("fast");
  const [webSearch, setWebSearch] = useState(false);
  const [attachedImages, setAttachedImages] = useState<string[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Active model (read from localStorage or default)
  const activeModel = "Groq / llama-3.3-70b";

  // ── Scroll logic ──────────────────────────────────────
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(scrollToBottom, [messages, scrollToBottom]);

  const handleScroll = useCallback(() => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    setShowScrollBtn(scrollHeight - scrollTop - clientHeight > 100);
  }, []);

  // ── Auto-resize textarea ─────────────────────────────
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + "px";
    }
  }, [input]);

  // ── File handling ─────────────────────────────────────
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    Array.from(files).forEach((file) => {
      if (!file.type.startsWith("image/")) {
        toast.error("Apenas imagens são suportadas por enquanto");
        return;
      }
      const reader = new FileReader();
      reader.onload = (ev) => {
        if (ev.target?.result) {
          setAttachedImages((prev) => [...prev, ev.target!.result as string]);
        }
      };
      reader.readAsDataURL(file);
    });

    setDrawerOpen(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeImage = (index: number) => {
    setAttachedImages((prev) => prev.filter((_, i) => i !== index));
  };

  // ── Copy message ──────────────────────────────────────
  const copyMessage = (msg: ChatMessage) => {
    navigator.clipboard.writeText(msg.content);
    setCopiedId(msg.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const shareMessage = (msg: ChatMessage) => {
    if (navigator.share) {
      navigator.share({ text: msg.content }).catch(() => {});
    } else {
      navigator.clipboard.writeText(msg.content);
      toast.success("Copiado para compartilhar");
    }
  };

  // ── Reasoning toggle ─────────────────────────────────
  const toggleReasoning = async () => {
    const next = reasoningMode === "fast" ? "planning" : "fast";
    setReasoningMode(next);
    try {
      if (isApiConfigured()) {
        await patchSettings({ reasoning_mode: next });
      }
    } catch {
      // silent
    }
    toast.success(next === "planning" ? "Raciocínio profundo ativado" : "Modo rápido ativado");
  };

  // ── Send message ──────────────────────────────────────
  const handleSend = async () => {
    const text = input.trim();
    if ((!text && attachedImages.length === 0) || isTyping) return;

    setInput("");
    setDrawerOpen(false);
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    const userMsg = createChatMessage("user", text);
    if (attachedImages.length > 0) {
      userMsg.images = [...attachedImages];
    }
    setAttachedImages([]);
    setMessages((prev) => [...prev, userMsg]);
    setIsTyping(true);

    await new Promise((r) => setTimeout(r, 800 + Math.random() * 1200));

    const response = getMockResponse();
    const assistantMsg = createChatMessage("assistant", "");
    setMessages((prev) => [...prev, assistantMsg]);

    let accumulated = "";
    const words = response.split(" ");
    for (let i = 0; i < words.length; i++) {
      accumulated += (i > 0 ? " " : "") + words[i];
      const currentText = accumulated;
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantMsg.id ? { ...m, content: currentText } : m))
      );
      await new Promise((r) => setTimeout(r, 20 + Math.random() * 30));
    }

    setIsTyping(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setInput("");
    setIsTyping(false);
    setAttachedImages([]);
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full">
      {/* ── Chat Header ─────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/30 min-h-[44px]">
        <div className="flex items-center gap-2 pl-12 md:pl-0">
          <div className="w-5 h-5 rounded-md gradient-cyber flex items-center justify-center">
            <Sparkles className="h-2.5 w-2.5 text-primary-foreground" />
          </div>
          <span className="text-xs font-medium text-foreground truncate max-w-[180px]">{activeModel}</span>
          {webSearch && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-mono shrink-0">
              🌐
            </span>
          )}
          {reasoningMode === "planning" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent font-mono shrink-0">
              ✳️
            </span>
          )}
        </div>
        {!isEmpty && (
          <button
            onClick={handleNewChat}
            className="text-[11px] text-muted-foreground hover:text-foreground active:text-foreground transition-colors font-mono px-2 py-1 -mr-2 min-h-[44px] flex items-center"
          >
            Nova conversa
          </button>
        )}
      </div>

      {/* ── Messages area ───────────────────────────── */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto scrollbar-cyber relative"
      >
        {isEmpty ? (
          <div className="h-full flex flex-col items-center justify-center px-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="text-center max-w-lg"
            >
              <div className="w-12 h-12 rounded-2xl gradient-cyber flex items-center justify-center mx-auto mb-6">
                <Sparkles className="h-6 w-6 text-primary-foreground" />
              </div>
              <h1 className="text-2xl font-semibold text-foreground mb-2">
                Como posso ajudar?
              </h1>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Posso analisar dados, buscar na base de conhecimento ou coordenar agentes para tarefas complexas.
              </p>
            </motion.div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-4 md:px-6 py-4 space-y-5">
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                >
                  {msg.role === "user" ? (
                    <div className="flex justify-end">
                      <div className="max-w-[85%]">
                        {msg.images && msg.images.length > 0 && (
                          <div className="flex gap-2 mb-2 justify-end flex-wrap">
                            {msg.images.map((img, idx) => (
                              <img
                                key={idx}
                                src={img}
                                alt="Anexo"
                                className="rounded-xl max-h-40 max-w-[200px] object-cover border border-border/50"
                              />
                            ))}
                          </div>
                        )}
                        {msg.content && (
                          <div className="rounded-2xl bg-muted px-4 py-3">
                            <p className="text-sm text-foreground whitespace-pre-wrap">{msg.content}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-1 group/msg">
                      <div className="flex items-center gap-2 mb-2">
                        <div className="w-6 h-6 rounded-lg gradient-cyber flex items-center justify-center">
                          <Sparkles className="h-3 w-3 text-primary-foreground" />
                        </div>
                        <span className="text-xs font-medium text-muted-foreground">IARA</span>
                      </div>
                      <div className="pl-8 prose prose-sm prose-invert max-w-none
                        [&_pre]:bg-muted [&_pre]:rounded-xl [&_pre]:p-3 [&_pre]:md:p-4 [&_pre]:font-mono [&_pre]:text-xs [&_pre]:border [&_pre]:border-border/50 [&_pre]:overflow-x-auto [&_pre]:-mx-2 [&_pre]:md:mx-0
                        [&_code]:text-primary [&_code]:font-mono [&_code]:text-xs [&_code]:bg-muted/60 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded-md
                        [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-foreground/90
                        [&_strong]:text-foreground [&_strong]:font-semibold
                        [&_blockquote]:border-l-primary/30 [&_blockquote]:text-muted-foreground [&_blockquote]:bg-muted/20 [&_blockquote]:rounded-r-lg [&_blockquote]:py-2 [&_blockquote]:px-4
                        [&_li]:text-foreground/90 [&_p]:text-foreground/90
                        [&_h1]:text-foreground [&_h2]:text-foreground [&_h3]:text-foreground
                        [&_a]:text-primary [&_a]:no-underline hover:[&_a]:underline
                        [&_hr]:border-border/30">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>

                      {/* Action buttons — visible on mobile, hover on desktop */}
                      {msg.content && (
                        <div className="pl-8 flex items-center gap-1 mt-2 md:opacity-0 md:group-hover/msg:opacity-100 transition-opacity">
                          <button
                            onClick={() => copyMessage(msg)}
                            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-mono text-muted-foreground hover:text-foreground active:text-foreground hover:bg-muted/50 active:bg-muted/50 transition-colors min-h-[36px]"
                          >
                            {copiedId === msg.id ? (
                              <Check className="h-3.5 w-3.5 text-success" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                            {copiedId === msg.id ? "Copiado" : "Copiar"}
                          </button>
                          <button
                            onClick={() => shareMessage(msg)}
                            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-mono text-muted-foreground hover:text-foreground active:text-foreground hover:bg-muted/50 active:bg-muted/50 transition-colors min-h-[36px]"
                          >
                            <Share2 className="h-3.5 w-3.5" />
                            Compartilhar
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {isTyping && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-6 h-6 rounded-lg gradient-cyber flex items-center justify-center">
                    <Sparkles className="h-3 w-3 text-primary-foreground" />
                  </div>
                  <span className="text-xs font-medium text-muted-foreground">IARA</span>
                  {reasoningMode === "planning" && (
                    <span className="text-[10px] text-accent font-mono animate-pulse">pensando...</span>
                  )}
                </div>
                <div className="pl-8 flex gap-1.5 items-center py-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse" style={{ animationDelay: "300ms" }} />
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Scroll-to-bottom FAB */}
        <AnimatePresence>
          {showScrollBtn && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              onClick={scrollToBottom}
              className="fixed bottom-32 right-4 md:right-6 z-30 w-10 h-10 rounded-full bg-card border border-border shadow-lg flex items-center justify-center text-muted-foreground hover:text-foreground active:text-foreground active:bg-muted transition-colors"
            >
              <ChevronDown className="h-5 w-5" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* ── Input area ──────────────────────────────── */}
      <div className="border-t border-border/50 bg-background px-4 py-2 pb-[env(safe-area-inset-bottom,8px)]">
        <div className="max-w-3xl mx-auto relative">
          {/* Attached image previews */}
          {attachedImages.length > 0 && (
            <div className="flex gap-2 mb-2 flex-wrap">
              {attachedImages.map((img, idx) => (
                <div key={idx} className="relative">
                  <img
                    src={img}
                    alt="Preview"
                    className="h-16 w-16 rounded-lg object-cover border border-border/50"
                  />
                  <button
                    onClick={() => removeImage(idx)}
                    className="absolute -top-1.5 -right-1.5 w-6 h-6 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Main input container */}
          <div className="relative flex flex-col rounded-2xl border border-border bg-card shadow-sm focus-within:border-primary/30 transition-colors">
            {/* Textarea row */}
            <div className="flex items-end gap-2 px-3 py-2.5">
              <button
                onClick={() => setDrawerOpen(!drawerOpen)}
                className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${
                  drawerOpen
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground active:text-foreground hover:bg-muted active:bg-muted"
                }`}
                title="Opções"
              >
                <Plus className={`h-5 w-5 transition-transform ${drawerOpen ? "rotate-45" : ""}`} />
              </button>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Pergunte qualquer coisa..."
                rows={1}
                className="flex-1 bg-transparent text-[15px] md:text-sm text-foreground placeholder-muted-foreground resize-none outline-none py-2 max-h-[200px] font-sans leading-relaxed"
              />
              <button
                onClick={handleSend}
                disabled={(!input.trim() && attachedImages.length === 0) || isTyping}
                className="shrink-0 w-10 h-10 rounded-xl flex items-center justify-center bg-primary text-primary-foreground disabled:opacity-30 transition-all hover:bg-primary/90 active:bg-primary/80"
              >
                {isTyping ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5" />
                )}
              </button>
            </div>

            {/* Chips toolbar */}
            <div className="flex items-center gap-2 px-3 pb-2.5 pt-0 overflow-x-auto scrollbar-cyber">
              <button
                onClick={() => setWebSearch(!webSearch)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-[12px] font-medium transition-all shrink-0 min-h-[36px] ${
                  webSearch
                    ? "bg-primary/15 text-primary border border-primary/30"
                    : "bg-muted/40 text-muted-foreground hover:text-foreground active:text-foreground hover:bg-muted/60 active:bg-muted/60 border border-transparent"
                }`}
              >
                <Globe className="h-3.5 w-3.5" />
                Pesquisar
                {webSearch && <Check className="h-3.5 w-3.5" />}
              </button>

              <button
                onClick={toggleReasoning}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-[12px] font-medium transition-all shrink-0 min-h-[36px] ${
                  reasoningMode === "planning"
                    ? "bg-accent/15 text-accent border border-accent/30"
                    : "bg-muted/40 text-muted-foreground hover:text-foreground active:text-foreground hover:bg-muted/60 active:bg-muted/60 border border-transparent"
                }`}
              >
                <ReasoningIcon className="h-3.5 w-3.5" />
                Raciocínio
                {reasoningMode === "planning" && <Check className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          {/* ── Drawer (overlay, floats above chat) ──── */}
          <AnimatePresence>
            {drawerOpen && (
              <>
                <div
                  className="fixed inset-0 z-40 bg-black/20"
                  onClick={() => setDrawerOpen(false)}
                />
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="absolute bottom-full left-0 right-0 mb-2 z-50"
                >
                  <div className="rounded-2xl border border-border bg-card p-4 shadow-lg">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-medium text-foreground">Opções</span>
                      <button
                        onClick={() => setDrawerOpen(false)}
                        className="w-9 h-9 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground active:text-foreground active:bg-muted transition-colors"
                      >
                        <X className="h-5 w-5" />
                      </button>
                    </div>

                    {/* Media chips */}
                    <div className="flex gap-3 mb-4">
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="flex flex-col items-center gap-2 px-6 py-4 rounded-xl bg-muted/40 hover:bg-muted/60 active:bg-muted/60 transition-colors min-w-[80px]"
                      >
                        <ImageIcon className="h-6 w-6 text-muted-foreground" />
                        <span className="text-[11px] text-muted-foreground">Imagem</span>
                      </button>
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="flex flex-col items-center gap-2 px-6 py-4 rounded-xl bg-muted/40 hover:bg-muted/60 active:bg-muted/60 transition-colors min-w-[80px]"
                      >
                        <Paperclip className="h-6 w-6 text-muted-foreground" />
                        <span className="text-[11px] text-muted-foreground">Arquivo</span>
                      </button>
                    </div>

                    {/* Actions */}
                    <div className="space-y-1">
                      <button
                        onClick={handleNewChat}
                        className="w-full flex items-center gap-3 px-3 py-3 rounded-xl text-sm text-muted-foreground hover:text-foreground active:text-foreground hover:bg-muted/40 active:bg-muted/40 transition-colors min-h-[44px]"
                      >
                        <Plus className="h-5 w-5" />
                        Nova conversa
                      </button>
                    </div>
                  </div>
                </motion.div>
              </>
            )}
          </AnimatePresence>

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={handleFileSelect}
          />

          <p className="text-center text-[10px] text-muted-foreground/60 mt-1.5">
            IARA pode cometer erros. Verifique informações importantes.
          </p>
        </div>
      </div>
    </div>
  );
}
