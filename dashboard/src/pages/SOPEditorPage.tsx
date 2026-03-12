import { useState } from "react";
import { motion } from "framer-motion";
import { FileText, Eye, Edit3, Save, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { isApiConfigured } from "@/lib/api-client";

const defaultSOPs: Record<string, string> = {
  corretor: `# SOP — Corretor (Broker Agent)

## Objetivo
Você é um corretor especializado em análise de investimentos. Seu papel é fornecer recomendações fundamentadas.

## Regras
1. **Sempre cite fontes** de dados financeiros
2. **Nunca recomende** sem análise de risco
3. Use linguagem técnica mas acessível
4. Considere perfil conservador com foco em dividendos

## Fluxo de Trabalho
\`\`\`
1. Receber solicitação → Classificar tipo (Análise/Recomendação/Relatório)
2. Consultar bases → LightRAG + APIs externas
3. Validar dados → Cross-reference com Council
4. Formatar resposta → Markdown estruturado
\`\`\`

## Métricas de Qualidade
- Precisão > 95%
- Tempo de resposta < 5s
- Citações por resposta ≥ 2
`,
  pesquisador: `# SOP — Pesquisador (Researcher Agent)

## Objetivo
Você é um pesquisador que busca e sintetiza informações de múltiplas fontes.

## Regras
1. **Busca exaustiva** — use pelo menos 3 fontes diferentes
2. **Resumo executivo** sempre no início
3. Indique nível de confiança (Alta/Média/Baixa)
4. Marque informações desatualizadas

## Ferramentas Disponíveis
- \`web_search(query)\` — Busca na internet
- \`rag_search(query)\` — Busca no LightRAG
- \`memory_recall(topic)\` — Busca no Mem0

## Template de Resposta
\`\`\`markdown
## Resumo
[Resumo executivo em 2-3 linhas]

## Descobertas
- Ponto 1 (Fonte: X, Confiança: Alta)
- Ponto 2 (Fonte: Y, Confiança: Média)

## Referências
1. [Título](url)
\`\`\`
`,
  analista: `# SOP — Analista (Analyst Agent)

## Objetivo
Analisar dados quantitativos e gerar insights acionáveis.

## Regras
1. **Sempre inclua números** — sem análise vaga
2. Use gráficos quando possível
3. Compare com benchmarks do setor
4. Identifique tendências e anomalias

## Métricas Padrão
| Métrica | Fórmula | Alvo |
|---------|---------|------|
| CAC | Custo Marketing / Novos Clientes | < R$50 |
| LTV | ARPU × Tempo Médio | > 12× CAC |
| Churn | Cancelados / Total | < 3% |

## Formato de Saída
Sempre retornar em JSON estruturado para integração com dashboards.
`,
};

export default function SOPEditorPage() {
  const [activeDoc, setActiveDoc] = useState<string>("corretor");
  const [docs, setDocs] = useState<Record<string, string>>(defaultSOPs);
  const [isPreview, setIsPreview] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    // In real app: POST /settings/sops with the doc content
    await new Promise((r) => setTimeout(r, 800));
    toast.success(`SOP "${activeDoc}" salva com sucesso`);
    setSaving(false);
  };

  const tabs = Object.keys(docs);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 md:p-6 pb-3 pt-12 md:pt-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold gradient-cyber-text">Editor de SOPs</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Instruções dos agentes — Markdown com Live Preview
              {!isApiConfigured() && <span className="ml-2 text-warning font-mono text-[10px]">• LOCAL</span>}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsPreview(!isPreview)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors min-h-[36px] ${
                isPreview
                  ? "bg-primary/15 text-primary"
                  : "glass text-muted-foreground hover:text-foreground"
              }`}
            >
              {isPreview ? <Eye className="h-3.5 w-3.5" /> : <Edit3 className="h-3.5 w-3.5" />}
              {isPreview ? "Preview" : "Editor"}
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg gradient-cyber text-primary-foreground text-xs font-medium min-h-[36px] disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Salvar
            </button>
          </div>
        </div>
      </div>

      {/* Doc tabs */}
      <div className="px-4 md:px-6 flex gap-1 overflow-x-auto scrollbar-cyber pb-2">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveDoc(tab)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-mono capitalize whitespace-nowrap transition-all min-h-[40px] ${
              activeDoc === tab
                ? "neon-border-cyan bg-primary/10 text-primary"
                : "glass text-muted-foreground hover:text-foreground"
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            {tab}
          </button>
        ))}
      </div>

      {/* Editor / Preview */}
      <div className="flex-1 px-4 md:px-6 py-3 overflow-hidden">
        {isPreview ? (
          /* Split view: editor left, preview right (on desktop) */
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
            <div className="glass-card overflow-hidden flex flex-col">
              <div className="px-3 py-2 border-b border-border/30 text-[10px] font-mono text-muted-foreground flex items-center gap-1.5">
                <Edit3 className="h-3 w-3" /> Editor
              </div>
              <textarea
                value={docs[activeDoc]}
                onChange={(e) => setDocs((prev) => ({ ...prev, [activeDoc]: e.target.value }))}
                className="flex-1 bg-transparent text-sm text-foreground font-mono p-4 resize-none outline-none leading-relaxed scrollbar-cyber"
                spellCheck={false}
              />
            </div>
            <div className="glass-card overflow-hidden flex flex-col">
              <div className="px-3 py-2 border-b border-border/30 text-[10px] font-mono text-muted-foreground flex items-center gap-1.5">
                <Eye className="h-3 w-3" /> Preview
              </div>
              <div className="flex-1 overflow-y-auto scrollbar-cyber p-4 prose prose-sm prose-invert max-w-none
                [&_pre]:bg-muted [&_pre]:rounded-xl [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-xs [&_pre]:border [&_pre]:border-border/50
                [&_code]:text-primary [&_code]:font-mono [&_code]:text-xs [&_code]:bg-muted/60 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded-md
                [&_pre_code]:bg-transparent [&_pre_code]:p-0
                [&_table]:w-full [&_th]:text-left [&_th]:text-foreground [&_th]:border-b [&_th]:border-border [&_th]:pb-2 [&_td]:border-b [&_td]:border-border/30 [&_td]:py-2
                [&_strong]:text-foreground [&_p]:text-foreground/90 [&_li]:text-foreground/90 [&_h1]:text-foreground [&_h2]:text-foreground [&_h3]:text-foreground">
                <ReactMarkdown>{docs[activeDoc]}</ReactMarkdown>
              </div>
            </div>
          </div>
        ) : (
          /* Editor only - full width */
          <div className="glass-card h-full overflow-hidden flex flex-col">
            <div className="px-3 py-2 border-b border-border/30 flex items-center justify-between">
              <span className="text-[10px] font-mono text-muted-foreground flex items-center gap-1.5">
                <Edit3 className="h-3 w-3" /> {activeDoc}.md
              </span>
              <span className="text-[10px] font-mono text-muted-foreground">
                {docs[activeDoc].split("\n").length} linhas
              </span>
            </div>
            <textarea
              value={docs[activeDoc]}
              onChange={(e) => setDocs((prev) => ({ ...prev, [activeDoc]: e.target.value }))}
              className="flex-1 bg-transparent text-sm text-foreground font-mono p-4 resize-none outline-none leading-relaxed scrollbar-cyber"
              spellCheck={false}
            />
          </div>
        )}
      </div>
    </div>
  );
}
