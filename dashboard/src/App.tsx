import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DashboardLayout } from "@/components/DashboardLayout";
import ChatPage from "@/pages/ChatPage";
import StatusPage from "@/pages/StatusPage";
import TerminalPage from "@/pages/TerminalPage";
import MemoryPage from "@/pages/MemoryPage";
import MetricsPage from "@/pages/MetricsPage";
import KnowledgePage from "@/pages/KnowledgePage";
import PlaygroundPage from "@/pages/PlaygroundPage";
import SOPEditorPage from "@/pages/SOPEditorPage";
import SettingsPage from "@/pages/SettingsPage";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Sonner
        toastOptions={{
          style: {
            background: "hsl(0, 0%, 7%)",
            border: "1px solid hsl(0, 0%, 14%)",
            color: "hsl(0, 0%, 90%)",
          },
        }}
      />
      <BrowserRouter>
        <Routes>
          <Route
            path="/*"
            element={
              <DashboardLayout>
                <Routes>
                  <Route path="/" element={<ChatPage />} />
                  <Route path="/status" element={<StatusPage />} />
                  <Route path="/terminal" element={<TerminalPage />} />
                  <Route path="/memory" element={<MemoryPage />} />
                  <Route path="/metrics" element={<MetricsPage />} />
                  <Route path="/knowledge" element={<KnowledgePage />} />
                  <Route path="/playground" element={<PlaygroundPage />} />
                  <Route path="/sop-editor" element={<SOPEditorPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </DashboardLayout>
            }
          />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
