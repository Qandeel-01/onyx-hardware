import { useSessionWebSocket } from './hooks/useSessionWebSocket';
import { useSession } from './store/sessionStore';

export default function App() {
  const session = useSession();

  useSessionWebSocket({
    url: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws`,
    sessionId: session?.id || '',
    token: localStorage.getItem('access_token') || '',
    onMessage: (msg) => console.log('WebSocket message:', msg),
    onError: (err) => console.error('WebSocket error:', err),
    maxRetries: 5,
    retryDelay: 1000,
    debug: true,
  });

  return (
    <div className="w-full h-full flex flex-col items-center justify-center bg-gray-900">
      <h1 className="text-4xl font-bold text-white mb-4">ONYX Analytics</h1>
      <p className="text-gray-400">Padel Shot Analysis Platform</p>
      {session ? (
        <div className="mt-8 p-4 bg-gray-800 rounded">
          <p className="text-green-400">Session Connected: {session.id}</p>
        </div>
      ) : (
        <div className="mt-8 p-4 bg-gray-800 rounded">
          <p className="text-yellow-400">Waiting for session...</p>
        </div>
      )}
    </div>
  );
}
