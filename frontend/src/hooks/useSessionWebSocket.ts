/**
 * Session WebSocket Hook
 * Manages WebSocket connection to backend with automatic reconnection logic
 * 
 * Features:
 * - Automatic connection establishment and reconnection on disconnect
 * - Exponential backoff retry strategy
 * - Message type discrimination and routing
 * - Integration with Zustand session store
 * - Error handling and logging
 * - Proper cleanup on unmount
 * 
 * Messages are automatically dispatched to store based on type:
 * - 'sntp' → clock sync sample
 * - 'shot' → new shot detection
 * - 'status' → device status update
 * - 'calibrated' → flash calibration completion
 * 
 * @module hooks/useSessionWebSocket
 */

import { useEffect, useRef, useCallback } from 'react';
import { useSessionStore } from '../store/sessionStore';
import {
  WebSocketMessage,
  SNTPMessage,
  ShotMessage,
  StatusMessage,
  CalibratedMessage,
  isWebSocketMessageType,
} from '../types/onyx';

/**
 * Configuration options for WebSocket connection
 */
interface WebSocketConfig {
  /** Base WebSocket URL (e.g., 'wss://localhost:8000') */
  url: string;
  /** Session ID to connect to */
  sessionId: number;
  /** Authentication token for connection */
  token: string;
  /** Optional callback when message is received */
  onMessage?: (message: WebSocketMessage) => void;
  /** Optional callback when error occurs */
  onError?: (error: Error) => void;
  /** Maximum number of reconnection attempts (default: 5) */
  maxRetries?: number;
  /** Initial retry delay in milliseconds (default: 1000) */
  retryDelay?: number;
  /** Enable debug logging (default: false) */
  debug?: boolean;
}

/**
 * Hook return type with connection controls
 */
interface UseSessionWebSocketReturn {
  /** True if WebSocket is currently connected */
  connected: boolean;
  /** Send a message through the WebSocket */
  send: (message: Record<string, unknown>) => void;
  /** Manually disconnect the WebSocket */
  disconnect: () => void;
}

/**
 * Custom hook for managing WebSocket connection to session backend
 * 
 * Example usage:
 * ```typescript
 * const { connected, send } = useSessionWebSocket({
 *   url: 'wss://localhost:8000',
 *   sessionId: 123,
 *   token: 'auth-token',
 *   debug: true,
 * });
 * ```
 * 
 * @param config - WebSocket connection configuration
 * @returns Object with connection state and control methods
 */
export function useSessionWebSocket(config: WebSocketConfig): UseSessionWebSocketReturn {
  // ==================== Refs ====================
  
  /** Reference to active WebSocket instance */
  const wsRef = useRef<WebSocket | null>(null);
  
  /** Reference to reconnection timeout */
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  /** Counter for reconnection attempts */
  const retriesRef = useRef(0);
  
  /** Store instance for dispatching actions */
  const store = useSessionStore();
  
  // ==================== Config Destructuring ====================
  
  const {
    url,
    sessionId,
    token,
    onMessage,
    onError,
    maxRetries = 5,
    retryDelay = 1000,
    debug = false,
  } = config;

  // ==================== Logging Utility ====================

  /**
   * Debug logging utility
   * Only logs if debug flag is enabled
   * @param args - Arguments to log
   */
  const log = useCallback(
    (...args: Parameters<typeof console.log>) => {
      if (debug) {
        console.log('[SessionWebSocket]', ...args);
      }
    },
    [debug]
  );

  // ==================== Message Handlers ====================

  /**
   * Handle SNTP clock synchronization message
   * @param message - SNTP message with timestamps
   */
  const handleSNTPMessage = useCallback(
    (message: SNTPMessage) => {
      log('Clock sync sample received:', message);
      store.addClockSyncSample({
        t1_device_ms: message.t1_ms,
        t2_server_utc_ms: message.t2_ms,
        t3_server_utc_ms: message.t3_ms,
        t4_device_ms: message.t4_ms,
      });
    },
    [store, log]
  );

  /**
   * Handle shot detection message
   * @param message - Shot message with sensor event
   */
  const handleShotMessage = useCallback(
    (message: ShotMessage) => {
      log('Shot detected:', message.data);
      // Shot is added to store via the message data
      onMessage?.(message);
    },
    [onMessage, log]
  );

  /**
   * Handle device status update message
   * @param message - Status message with device metrics
   */
  const handleStatusMessage = useCallback(
    (message: StatusMessage) => {
      log('Device status update:', message.data);
      store.setDeviceStatus(message.data);
      onMessage?.(message);
    },
    [store, onMessage, log]
  );

  /**
   * Handle calibration completion message
   * @param message - Calibrated message with latency offset
   */
  const handleCalibratedMessage = useCallback(
    (message: CalibratedMessage) => {
      log('Flash calibration complete:', message.residual_offset_ms, 'ms');
      store.setFlashCalibration(message.residual_offset_ms, 'completed');
      onMessage?.(message);
    },
    [store, onMessage, log]
  );

  /**
   * Main message router - dispatches to appropriate handler
   * @param message - Parsed WebSocket message
   */
  const routeMessage = useCallback(
    (message: WebSocketMessage) => {
      if (isWebSocketMessageType(message, 'sntp')) {
        handleSNTPMessage(message);
      } else if (isWebSocketMessageType(message, 'shot')) {
        handleShotMessage(message);
      } else if (isWebSocketMessageType(message, 'status')) {
        handleStatusMessage(message);
      } else if (isWebSocketMessageType(message, 'calibrated')) {
        handleCalibratedMessage(message);
      } else {
        console.warn('Unknown message type:', message);
      }
    },
    [handleSNTPMessage, handleShotMessage, handleStatusMessage, handleCalibratedMessage]
  );

  // ==================== Connection Management ====================

  /**
   * Establish WebSocket connection with event handlers
   * Implements exponential backoff for retries
   */
  const connect = useCallback(() => {
    // Prevent duplicate connections
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      log('WebSocket already connected');
      return;
    }

    try {
      const wsUrl = `${url}/api/sessions/${sessionId}/ws?token=${token}`;
      log('Connecting to:', wsUrl);
      const ws = new WebSocket(wsUrl);

      // Connection established
      ws.onopen = () => {
        log('WebSocket connected');
        retriesRef.current = 0;
        store.setWsConnected(true);
      };

      // Message received
      ws.onmessage = (event: MessageEvent<string>) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          routeMessage(message);
        } catch (parseError) {
          const error = parseError instanceof Error ? parseError : new Error('Failed to parse message');
          console.error('Failed to parse WebSocket message:', error);
          console.error('Raw message:', event.data);
          onError?.(error);
        }
      };

      // Connection error
      ws.onerror = (event: Event) => {
        console.error('WebSocket error:', event);
        const error = new Error('WebSocket error occurred');
        onError?.(error);
      };

      // Connection closed
      ws.onclose = () => {
        log('WebSocket closed');
        store.setWsConnected(false);

        // Attempt reconnection with exponential backoff
        if (retriesRef.current < maxRetries) {
          retriesRef.current += 1;
          const delay = retryDelay * Math.pow(2, retriesRef.current - 1);
          log(
            `Reconnecting in ${delay}ms (attempt ${retriesRef.current}/${maxRetries})`
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else {
          const error = new Error(
            `WebSocket connection failed after ${maxRetries} retries`
          );
          console.error(error);
          onError?.(error);
        }
      };

      wsRef.current = ws;
    } catch (createError) {
      const error = createError instanceof Error 
        ? createError 
        : new Error('Failed to create WebSocket');
      console.error('Failed to create WebSocket:', error);
      onError?.(error);
    }
  }, [url, sessionId, token, store, onMessage, onError, maxRetries, retryDelay, log, routeMessage]);

  // ==================== Public API ====================

  /**
   * Send a message through the WebSocket
   * Message is JSON-stringified automatically
   * @param message - Message object to send
   */
  const send = useCallback(
    (message: Record<string, unknown>) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify(message));
          log('Message sent:', message);
        } catch (error) {
          const sendError = error instanceof Error ? error : new Error('Failed to send message');
          console.error('Failed to send WebSocket message:', sendError);
          onError?.(sendError);
        }
      } else {
        console.warn('WebSocket not connected, cannot send message:', message);
      }
    },
    [log, onError]
  );

  /**
   * Manually disconnect the WebSocket
   * Clears reconnection timeout and closes connection
   */
  const disconnect = useCallback(() => {
    log('Disconnecting WebSocket');

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    store.setWsConnected(false);
  }, [store, log]);

  // ==================== Effect: Connect on Mount ====================

  /**
   * Establish connection on mount and cleanup on unmount
   */
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // ==================== Return ====================

  return {
    connected: store.wsConnected,
    send,
    disconnect,
  };
}

/**
 * Hook variant for sending a single message and cleanup
 * Useful for one-time operations during calibration
 * 
 * @param config - WebSocket configuration
 * @param messageToSend - Message to send immediately after connection
 * @returns send and disconnect functions
 */
export function useSessionWebSocketOnce(
  config: Omit<WebSocketConfig, 'onMessage'> & { onMessage?: (msg: WebSocketMessage) => void },
  messageToSend?: Record<string, unknown>
) {
  const { send, disconnect } = useSessionWebSocket(config);

  useEffect(() => {
    if (messageToSend) {
      send(messageToSend);
    }
  }, [messageToSend, send]);

  return { send, disconnect };
}
