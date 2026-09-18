import { useCallback, useEffect, useRef, useState } from "react";

export type WsStatus = "connecting" | "connected" | "disconnected" | "error";

interface Options {
  onMessage: (data: unknown) => void;
  maxReconnectDelay?: number;
}

export function useWebSocket(url: string, { onMessage, maxReconnectDelay = 30_000 }: Options) {
  const [status, setStatus]         = useState<WsStatus>("connecting");
  const wsRef                       = useRef<WebSocket | null>(null);
  const reconnectDelay              = useRef(1_000);
  const isMounted                   = useRef(true);
  const reconnectTimer              = useRef<number | null>(null);
  const onMessageRef                = useRef(onMessage);
  onMessageRef.current              = onMessage;

  // Only close a socket that finished handshaking. Calling .close() on a
  // CONNECTING socket produces "WebSocket is closed before the connection
  // is established" and, in React 18 StrictMode, runs on every dev mount.
  const safeClose = (ws: WebSocket | null) => {
    if (!ws) return;
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CLOSING) {
      ws.close();
    } else if (ws.readyState === WebSocket.CONNECTING) {
      // Suppress the warning by detaching handlers first; the socket will
      // still be reaped by the browser, but won't log or fire our callbacks.
      ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null;
      try { ws.close(); } catch { /* ignore */ }
    }
  };

  const connect = useCallback(() => {
    if (!isMounted.current) return;

    // Don't stack connections: if one is already open or in-flight, leave it.
    const existing = wsRef.current;
    if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStatus("connecting");
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMounted.current) { safeClose(ws); return; }
      setStatus("connected");
      reconnectDelay.current = 1_000;
    };

    ws.onmessage = (event: MessageEvent) => {
      try { onMessageRef.current(JSON.parse(event.data as string)); }
      catch { /* ignore malformed frames */ }
    };

    ws.onclose = () => {
      if (!isMounted.current) return;
      setStatus("disconnected");
      const delay = reconnectDelay.current;
      reconnectDelay.current = Math.min(delay * 2, maxReconnectDelay);
      if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
      reconnectTimer.current = window.setTimeout(connect, delay);
    };

    ws.onerror = () => {
      if (!isMounted.current) return;
      setStatus("error");
      try { ws.close(); } catch { /* ignore */ }
    };
  }, [url, maxReconnectDelay]);

  useEffect(() => {
    isMounted.current = true;
    connect();
    return () => {
      isMounted.current = false;
      if (reconnectTimer.current) {
        window.clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      safeClose(wsRef.current);
      wsRef.current = null;
    };
  }, [connect]);

  return { status };
}