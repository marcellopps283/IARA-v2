import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { Sparkles } from "lucide-react";
import { useSidebar } from "@/components/ui/sidebar";

function ToggleButton() {
  const { toggleSidebar } = useSidebar();
  return (
    <div className="absolute top-3 left-3 z-50">
      <button
        onClick={toggleSidebar}
        className="w-9 h-9 rounded-xl gradient-cyber flex items-center justify-center shadow-lg hover:opacity-80 transition-opacity"
      >
        <Sparkles className="h-4 w-4 text-primary-foreground" />
      </button>
    </div>
  );
}

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-background">
        <AppSidebar />
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
          <ToggleButton />
          {children}
        </main>
      </div>
    </SidebarProvider>
  );
}
