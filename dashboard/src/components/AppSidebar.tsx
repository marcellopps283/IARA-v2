import {
  MessageSquare,
  Activity,
  Terminal,
  Brain,
  BarChart3,
  Network,
  Sparkles,
  Settings,
  FlaskConical,
  FileText,
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useLocation } from "react-router-dom";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";

const navItems = [
  { title: "Chat", url: "/", icon: MessageSquare },
  { title: "Status", url: "/status", icon: Activity },
  { title: "Terminal", url: "/terminal", icon: Terminal },
  { title: "Memória", url: "/memory", icon: Brain },
  { title: "Métricas", url: "/metrics", icon: BarChart3 },
  { title: "Knowledge", url: "/knowledge", icon: Network },
  { title: "Playground", url: "/playground", icon: FlaskConical },
  { title: "SOPs", url: "/sop-editor", icon: FileText },
];

export function AppSidebar() {
  const { state, toggleSidebar } = useSidebar();
  const collapsed = state === "collapsed";
  const location = useLocation();

  return (
    <Sidebar collapsible="offcanvas" className="border-r border-border/50 bg-sidebar">
      <SidebarHeader className="p-3">
        <div className="flex items-center gap-2.5">
          <button
            onClick={toggleSidebar}
            className="w-8 h-8 rounded-xl gradient-cyber flex items-center justify-center shrink-0 hover:opacity-80 transition-opacity"
            title={collapsed ? "Expandir menu" : "Colapsar menu"}
          >
            <Sparkles className="h-4 w-4 text-primary-foreground" />
          </button>
          {!collapsed && (
            <span className="text-sm font-semibold text-foreground tracking-wide animate-fade-in">
              IARA
            </span>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent className="px-2">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-0.5">
              {navItems.map((item) => {
                const isActive = location.pathname === item.url;
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild>
                      <NavLink
                        to={item.url}
                        end
                        className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all duration-150 ${
                          isActive
                            ? "bg-muted text-foreground font-medium"
                            : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                        }`}
                        activeClassName=""
                      >
                        <item.icon className={`h-4 w-4 shrink-0 ${isActive ? "text-primary" : ""}`} />
                        {!collapsed && <span>{item.title}</span>}
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-3 space-y-2">
        {!collapsed && (
          <>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <NavLink
                    to="/settings"
                    end
                    className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all duration-150 ${
                      location.pathname === "/settings"
                        ? "bg-muted text-foreground font-medium"
                        : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                    }`}
                    activeClassName=""
                  >
                    <Settings className={`h-4 w-4 shrink-0 ${location.pathname === "/settings" ? "text-primary" : ""}`} />
                    <span>Configurações</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-muted/30 animate-fade-in">
              <div className="w-2 h-2 rounded-full bg-success shrink-0" />
              <span className="text-xs text-muted-foreground">Online</span>
              <span className="text-[10px] text-muted-foreground/60 ml-auto font-mono">v2.4.1</span>
            </div>
          </>
        )}
      </SidebarFooter>
    </Sidebar>
  );
}
