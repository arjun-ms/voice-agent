import { useState, useCallback, useRef, useEffect } from 'react'
import { LiveKitRoom, RoomAudioRenderer, useRemoteParticipants } from '@livekit/components-react'
import '@livekit/components-styles'
import ActiveCallInterface from './components/ActiveCallInterface'
import SummaryPanel from './components/SummaryPanel'
import AgentAvatar from './components/AgentAvatar'
import type { SummaryData } from './components/SummaryPanel'
import './App.css'

// Helper component to track when the agent joins the room
function AgentTracker({ onAgentJoined }: { onAgentJoined: () => void }) {
  const participants = useRemoteParticipants()
  useEffect(() => {
    if (participants.length > 0) {
      onAgentJoined()
    }
  }, [participants, onAgentJoined])
  return null
}

function App() {
  const [status, setStatus] = useState('Ready')
  const [token, setToken] = useState('')
  const [serverUrl, setServerUrl] = useState('')
  const [summaryData, setSummaryData] = useState<SummaryData | null>(null)
  const isConnectedRef = useRef(false)

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  const wakeUpServer = async (maxRetries = 5, delayMs = 3000): Promise<boolean> => {
    for (let i = 0; i < maxRetries; i++) {
      try {
        const res = await fetch(`${API_URL}/health`, { method: 'GET' })
        if (res.ok) return true
      } catch {
        // Server is asleep, show wake-up status and retry
        if (i === 0) setStatus('Waking up server...')
      }
      if (i < maxRetries - 1) {
        await new Promise(r => setTimeout(r, delayMs))
      }
    }
    return false
  }

  const handleStartCall = async () => {
    setStatus('Connecting...')
    setSummaryData(null)
    try {
      const isAwake = await wakeUpServer()
      if (!isAwake) {
        setStatus('Ready')
        console.error('Server failed to wake up after retries')
        return
      }
      setStatus('Connecting...')
      const response = await fetch(`${API_URL}/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ participant_name: 'Patient' })
      })
      const data = await response.json()
      if (data.token) { 
        setToken(data.token)
        setServerUrl(data.server_url || 'ws://localhost:7880')
      }
    } catch (e) {
      setStatus('Ready')
      console.error('Failed to start call', e)
    }
  }

  const doEndCall = useCallback(async () => {
    setStatus('Summary')
    setToken('')
    
    // Poll/Fetch for summary
    try {
      // Small delay since backend generates it asynchronously on disconnect
      await new Promise(r => setTimeout(r, 2000))
      
      const response = await fetch(`${API_URL}/api/summary/latest`)
      if (response.ok) {
        const data = await response.json()
        setSummaryData(data)
      } else {
        // If it fails, try once more after 3 seconds
        await new Promise(r => setTimeout(r, 3000))
        const retry = await fetch(`${API_URL}/api/summary/latest`)
        if (retry.ok) {
           setSummaryData(await retry.json())
        }
      }
    } catch (e) {
      console.error('Failed to fetch summary', e)
    }
  }, [API_URL])

  // Called by the End Call / Cancel buttons
  const handleEndCall = useCallback(async () => {
    isConnectedRef.current = false
    await doEndCall()
  }, [doEndCall])

  const handleConnected = useCallback(() => {
    console.log('LiveKit room connected')
    isConnectedRef.current = true
    setStatus('Waiting for agent...')
  }, [])

  const handleAgentJoined = useCallback(() => {
    console.log('Agent joined the room')
    setStatus('Agent joined')
  }, [])

  // Called by LiveKit onDisconnected - only runs if we were actually connected
  const handleDisconnected = useCallback(() => {
    console.log('LiveKit room disconnected, isConnected:', isConnectedRef.current)
    if (!isConnectedRef.current) return
    isConnectedRef.current = false
    doEndCall()
  }, [doEndCall])

  const handleError = useCallback((error: Error) => {
    console.error('LiveKit error:', error)
  }, [])

  return (
    <div className="app-container">
      <header>
        <h1>Mykare Health Agent</h1>
      </header>
      
      <main className="call-interface">
        {status === 'Summary' ? (
          <>
            <SummaryPanel data={summaryData} />
            <div className="controls" style={{ marginTop: '2rem', textAlign: 'center' }}>
              <button className="primary-btn" onClick={() => setStatus('Ready')}>
                Start New Call
              </button>
            </div>
          </>
        ) : (
          <>
            {/* When token exists, LiveKitRoom mounts and handles the avatar */}
            {!token && (
              <div data-testid="avatar-placeholder" className="avatar-placeholder"></div>
            )}
            
            {token && serverUrl && (
              <LiveKitRoom
                serverUrl={serverUrl}
                token={token}
                connect={true}
                audio={true}
                video={false}
                onConnected={handleConnected}
                onDisconnected={handleDisconnected}
                onError={handleError}
              >
                <AgentAvatar />
                <AgentTracker onAgentJoined={handleAgentJoined} />
                <RoomAudioRenderer />
                <ActiveCallInterface />
              </LiveKitRoom>
            )}

            {status !== 'Agent joined' && (
              <div className="status-text" style={{ minHeight: '3rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                {(status === 'Connecting...' || status === 'Waiting for agent...') && (
                  <div className="spinner" data-testid="loading-spinner"></div>
                )}
                {status}
              </div>
            )}
            
            <div className="controls">
              {status === 'Agent joined' && (
                <button type="button" className="danger-btn" onClick={handleEndCall}>
                  End Call
                </button>
              )}

              {status === 'Ready' && (
                <button 
                  type="button" 
                  className="primary-btn"
                  onClick={handleStartCall}
                >
                  Start Call
                </button>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export default App
