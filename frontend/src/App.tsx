/**
 * Main App component with routing
 */
import React, { useState } from 'react';
import { Session } from '@/types';
import { SessionManager } from '@/components/SessionManager';
import { LiveAnalysisDashboard } from '@/components/dashboard/LiveAnalysisDashboard';
import '@/index.css';

export const App: React.FC = () => {
  const [activeSession, setActiveSession] = useState<Session | null>(null);

  const handleSessionCreated = (session: Session) => {
    setActiveSession(session);
  };

  const handleBackToHome = () => {
    setActiveSession(null);
  };

  return (
    <div className="min-h-screen bg-primary">
      {!activeSession ? (
        <SessionManager onSessionCreated={handleSessionCreated} />
      ) : (
        <>
          <button
            onClick={handleBackToHome}
            className="fixed top-6 left-6 px-4 py-2 bg-secondary hover:bg-gray-700 text-white rounded-lg transition-colors z-10"
          >
            ← Back
          </button>
          <LiveAnalysisDashboard sessionId={activeSession.id} />
        </>
      )}
    </div>
  );
};

export default App;
