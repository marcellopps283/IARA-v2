// API client for IARA backend
// Reads VITE_API_KEY and VITE_API_BASE_URL from environment

import type { StatusResponse, MemoryExplorerResponse, LogEntry } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY || "iara-secret-key";

function headers(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  };
}

// ── Status ──────────────────────────────────────────────
export async function fetchStatus(): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE}/status`, { headers: headers() });
  if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`);
  return res.json();
}

// ── Memory ──────────────────────────────────────────────
export async function fetchMemoryExplorer(): Promise<MemoryExplorerResponse> {
  const res = await fetch(`${API_BASE}/memory/explorer`, { headers: headers() });
  if (!res.ok) throw new Error(`Memory fetch failed: ${res.status}`);
  return res.json();
}

export async function resetWorkingMemory(): Promise<void> {
  const res = await fetch(`${API_BASE}/memory/working/reset`, {
    method: "POST",
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Reset failed: ${res.status}`);
}

export async function forceReindex(): Promise<void> {
  const res = await fetch(`${API_BASE}/memory/reindex`, {
    method: "POST",
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Reindex failed: ${res.status}`);
}

export async function deleteFact(factId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/memory/facts/${factId}`, {
    method: "DELETE",
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Delete fact failed: ${res.status}`);
}

export async function fetchFacts(): Promise<{ id: string; text: string; source: string; created: string }[]> {
  const res = await fetch(`${API_BASE}/memory/facts`, { headers: headers() });
  if (!res.ok) throw new Error(`Fetch facts failed: ${res.status}`);
  return res.json();
}

// ── Settings ────────────────────────────────────────────
export async function patchSettings(payload: {
  active_model?: string;
  backup_model?: string;
  temperature?: number;
  reasoning_mode?: string;
  log_level?: string;
}): Promise<void> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: "PATCH",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Settings update failed: ${res.status}`);
}

export async function saveApiKeys(keys: Record<string, string>): Promise<void> {
  const res = await fetch(`${API_BASE}/settings/keys`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify(keys),
  });
  if (!res.ok) throw new Error(`Save keys failed: ${res.status}`);
}

// ── System ──────────────────────────────────────────────
export async function restartContainer(): Promise<void> {
  const res = await fetch(`${API_BASE}/system/restart`, {
    method: "POST",
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Restart failed: ${res.status}`);
}

// ── WebSocket for logs ──────────────────────────────────
export function connectLogsWS(onMessage: (log: LogEntry) => void, onError?: (e: Event) => void): WebSocket {
  const wsBase = API_BASE.replace(/^http/, "ws");
  const url = `${wsBase}/ws/logs?api_key=${API_KEY}`;
  const ws = new WebSocket(url);

  ws.onmessage = (event) => {
    try {
      const log: LogEntry = JSON.parse(event.data);
      onMessage(log);
    } catch {
      // ignore malformed messages
    }
  };

  ws.onerror = (e) => onError?.(e);

  return ws;
}

// Check if API is configured (has a real URL, not just localhost)
export function isApiConfigured(): boolean {
  return !!import.meta.env.VITE_API_BASE_URL;
}
