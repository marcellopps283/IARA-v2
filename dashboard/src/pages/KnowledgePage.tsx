import { useState, useRef, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { Network, Search, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import ForceGraph2D from "react-force-graph-2d";

// Mock knowledge graph data
const mockGraphData = {
  nodes: [
    { id: "iara", label: "IARA Core", group: "system", val: 20 },
    { id: "lightrag", label: "LightRAG", group: "system", val: 15 },
    { id: "mem0", label: "Mem0", group: "system", val: 15 },
    { id: "qdrant", label: "Qdrant", group: "infra", val: 12 },
    { id: "redis", label: "Redis", group: "infra", val: 10 },
    { id: "swarm", label: "Swarm Agent", group: "agent", val: 14 },
    { id: "council", label: "Council", group: "agent", val: 14 },
    { id: "coder", label: "Coder Agent", group: "agent", val: 10 },
    { id: "researcher", label: "Researcher", group: "agent", val: 10 },
    { id: "analyst", label: "Analyst", group: "agent", val: 10 },
    { id: "python", label: "Python", group: "knowledge", val: 8 },
    { id: "fastapi", label: "FastAPI", group: "knowledge", val: 8 },
    { id: "react", label: "React", group: "knowledge", val: 8 },
    { id: "fintech", label: "Fintech", group: "knowledge", val: 8 },
    { id: "ml_pipeline", label: "ML Pipeline", group: "knowledge", val: 8 },
    { id: "investimentos", label: "Investimentos", group: "knowledge", val: 7 },
    { id: "dividendos", label: "Dividendos", group: "knowledge", val: 6 },
    { id: "cac", label: "CAC", group: "knowledge", val: 6 },
    { id: "churn", label: "Churn Rate", group: "knowledge", val: 6 },
    { id: "strategy_2025", label: "Strategy 2025", group: "document", val: 9 },
    { id: "q4_report", label: "Q4 Report", group: "document", val: 9 },
    { id: "sop_broker", label: "SOP Corretor", group: "document", val: 7 },
  ],
  links: [
    { source: "iara", target: "lightrag", label: "usa" },
    { source: "iara", target: "mem0", label: "persiste" },
    { source: "iara", target: "swarm", label: "orquestra" },
    { source: "iara", target: "council", label: "consulta" },
    { source: "lightrag", target: "qdrant", label: "armazena" },
    { source: "mem0", target: "redis", label: "cache" },
    { source: "swarm", target: "coder", label: "delega" },
    { source: "swarm", target: "researcher", label: "delega" },
    { source: "swarm", target: "analyst", label: "delega" },
    { source: "council", target: "analyst", label: "valida" },
    { source: "researcher", target: "lightrag", label: "busca" },
    { source: "coder", target: "python", label: "domina" },
    { source: "coder", target: "fastapi", label: "domina" },
    { source: "coder", target: "react", label: "domina" },
    { source: "analyst", target: "fintech", label: "analisa" },
    { source: "analyst", target: "ml_pipeline", label: "monitora" },
    { source: "fintech", target: "investimentos", label: "inclui" },
    { source: "investimentos", target: "dividendos", label: "foco" },
    { source: "fintech", target: "cac", label: "métrica" },
    { source: "fintech", target: "churn", label: "métrica" },
    { source: "lightrag", target: "strategy_2025", label: "indexou" },
    { source: "lightrag", target: "q4_report", label: "indexou" },
    { source: "lightrag", target: "sop_broker", label: "indexou" },
  ],
};

const groupColors: Record<string, string> = {
  system: "hsl(185, 100%, 50%)",
  infra: "hsl(142, 71%, 45%)",
  agent: "hsl(263, 70%, 58%)",
  knowledge: "hsl(38, 92%, 50%)",
  document: "hsl(0, 0%, 55%)",
};

export default function KnowledgePage() {
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  const [hoveredNode, setHoveredNode] = useState<any>(null);
  const [search, setSearch] = useState("");
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  // Search highlight
  useEffect(() => {
    if (!search.trim()) {
      setHighlightNodes(new Set());
      return;
    }
    const q = search.toLowerCase();
    const matches = new Set<string>();
    mockGraphData.nodes.forEach((n) => {
      if (n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)) {
        matches.add(n.id);
      }
    });
    setHighlightNodes(matches);
  }, [search]);

  const handleZoomIn = () => fgRef.current?.zoom(fgRef.current.zoom() * 1.3, 300);
  const handleZoomOut = () => fgRef.current?.zoom(fgRef.current.zoom() / 1.3, 300);
  const handleFit = () => fgRef.current?.zoomToFit(400, 40);

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.label || node.id;
      const fontSize = Math.max(10 / globalScale, 3);
      const r = Math.sqrt(node.val || 8) * 1.8;
      const color = groupColors[node.group] || "hsl(0,0%,55%)";
      const isHighlighted = highlightNodes.size === 0 || highlightNodes.has(node.id);
      const isHovered = hoveredNode?.id === node.id;

      // Glow
      if (isHovered) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
        ctx.fillStyle = color.replace(")", ", 0.2)").replace("hsl(", "hsla(");
        ctx.fill();
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = isHighlighted ? color : color.replace(")", ", 0.2)").replace("hsl(", "hsla(");
      ctx.fill();

      if (isHovered || globalScale > 1.5) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 1 / globalScale;
        ctx.stroke();
      }

      // Label
      if (globalScale > 0.8 || isHovered || isHighlighted) {
        ctx.font = `${isHovered ? "bold " : ""}${fontSize}px 'Space Grotesk', sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = isHighlighted
          ? "rgba(230,230,230,0.95)"
          : "rgba(230,230,230,0.3)";
        ctx.fillText(label, node.x, node.y + r + fontSize + 1);
      }
    },
    [highlightNodes, hoveredNode]
  );

  const linkColor = useCallback(
    (link: any) => {
      if (highlightNodes.size === 0) return "rgba(255,255,255,0.08)";
      const src = typeof link.source === "object" ? link.source.id : link.source;
      const tgt = typeof link.target === "object" ? link.target.id : link.target;
      if (highlightNodes.has(src) || highlightNodes.has(tgt)) return "rgba(255,255,255,0.2)";
      return "rgba(255,255,255,0.03)";
    },
    [highlightNodes]
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 md:p-6 pb-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold gradient-cyber-text">Knowledge Graph</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {mockGraphData.nodes.length} nós • {mockGraphData.links.length} conexões
            </p>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={handleZoomIn} className="w-9 h-9 rounded-lg glass flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors">
              <ZoomIn className="h-4 w-4" />
            </button>
            <button onClick={handleZoomOut} className="w-9 h-9 rounded-lg glass flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors">
              <ZoomOut className="h-4 w-4" />
            </button>
            <button onClick={handleFit} className="w-9 h-9 rounded-lg glass flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors">
              <Maximize2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Search + Legend */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="glass-card flex items-center gap-2 px-3 py-2 flex-1 min-w-[200px] max-w-sm">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar entidade..."
              className="bg-transparent text-sm text-foreground placeholder-muted-foreground outline-none flex-1 font-mono"
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(groupColors).map(([group, color]) => (
              <div key={group} className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                {group}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Graph container */}
      <div ref={containerRef} className="flex-1 relative overflow-hidden">
        <ForceGraph2D
          ref={fgRef}
          graphData={mockGraphData}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="transparent"
          nodeCanvasObject={nodeCanvasObject}
          nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
            const r = Math.sqrt(node.val || 8) * 1.8 + 4;
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          }}
          linkColor={linkColor}
          linkWidth={0.5}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={0.9}
          onNodeHover={setHoveredNode}
          onNodeClick={(node: any) => {
            fgRef.current?.centerAt(node.x, node.y, 500);
            fgRef.current?.zoom(3, 500);
          }}
          cooldownTicks={100}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.3}
        />

        {/* Tooltip */}
        {hoveredNode && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="absolute top-4 right-4 glass-card p-3 max-w-[200px] z-10"
          >
            <div className="flex items-center gap-2 mb-1">
              <div className="w-3 h-3 rounded-full" style={{ background: groupColors[hoveredNode.group] }} />
              <span className="text-sm font-semibold text-foreground">{hoveredNode.label}</span>
            </div>
            <span className="text-[10px] font-mono text-muted-foreground">
              Grupo: {hoveredNode.group} • ID: {hoveredNode.id}
            </span>
          </motion.div>
        )}
      </div>
    </div>
  );
}
