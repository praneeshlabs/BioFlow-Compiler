import { GoldenPathPreview, ProtocolState } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {}

export async function compileProtocol(rawText: string): Promise<ProtocolState> {
  const res = await fetch(`${API_BASE}/api/compile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: rawText }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || `Compile request failed (${res.status})`);
  }
  return res.json();
}

export async function fetchGoldenPaths(): Promise<GoldenPathPreview[]> {
  const res = await fetch(`${API_BASE}/api/golden-paths`);
  if (!res.ok) {
    throw new ApiError(`Failed to load example protocols (${res.status})`);
  }
  return res.json();
}
