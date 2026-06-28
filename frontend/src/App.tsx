import { useState, useCallback, useRef, useEffect } from 'react'
import { LiveKitRoom, RoomAudioRenderer, useRemoteParticipants, TrackToggle, Chat } from '@livekit/components-react'
import { Track } from 'livekit-client'
import '@livekit/components-styles'
import ActiveCallInterface from './components/ActiveCallInterface'
import SummaryPanel from './components/SummaryPanel'
// import AgentAvatar from './components/AgentAvatar'
import VideoCallAvatar from './components/VideoCallAvatar'
import type { SummaryData } from './components/SummaryPanel'
import './App.css'

// Helper component to track when the agent joins the room
function AgentTracker({ onAgentJoined }: { onAgentJoined: () => void }) {
  const participants = useRemoteParticipants()
  const hasJoined = useRef(false)
  useEffect(() => {
    if (participants.length > 0 && !hasJoined.current) {
      hasJoined.current = true
      onAgentJoined()
    }
  }, [participants, onAgentJoined])
  return null
}

function App() {
  const [status, setStatus] = useState('Ready')
  const [token, setToken] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [serverUrl, setServerUrl] = useState('')
  const [roomName, setRoomName] = useState('')
  const [summaryData, setSummaryData] = useState<SummaryData | null>(null)
  const [summaryError, setSummaryError] = useState<string>('')
  const isConnectedRef = useRef(false)

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  const wakeUpServer = async (maxRetries = 5, delayMs = 3000): Promise<boolean> => {
    for (let i = 0; i < maxRetries; i++) {
      try {
        const res = await fetch(`${API_URL}/ping`, { method: 'GET' })
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
    setSummaryError('')
    setErrorMsg('')
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
        setRoomName(data.room_name || '')
      }
    } catch (e) {
      setStatus('Ready')
      console.error('Failed to start call', e)
    }
  }

  const doEndCall = useCallback(async () => {
    setStatus('Summary')
    setToken('')
    
    // Poll/Fetch for summary with retries
    try {
      let found = false
      // Poll every 5 seconds, up to 6 times (30 seconds total)
      for (let i = 0; i < 6; i++) {
        await new Promise(r => setTimeout(r, 5000))
        
        if (!roomName) {
            console.error('No room name available to fetch summary.');
            break;
        }

        const response = await fetch(`${API_URL}/api/summary/room/${encodeURIComponent(roomName)}`)
        if (response.ok) {
          const data = await response.json()
          setSummaryData(data)
          found = true
          break
        }
      }
      if (!found) {
        console.error('Summary was not ready after 30 seconds of waiting.')
        setSummaryError('Unable to generate summary. The call may have been too short (under 10 seconds), or the AI agent encountered a network error while processing the transcript.')
      }
    } catch (e) {
      console.error('Failed to fetch summary', e)
      setSummaryError('Failed to fetch summary from the server due to a network error.')
    }
  }, [API_URL, roomName])

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
    if (error.message.includes('Abort handler called')) {
      // Ignore errors caused by React StrictMode unmounting the component during connection
      return;
    }
    if (error.message.includes('NotReadableError') || error.message.includes('Could not start audio source')) {
      setErrorMsg('Microphone blocked! You can still hear the agent and type messages to her below.')
    } else {
      setErrorMsg(`Connection error: ${error.message}`)
    }
  }, [])

  return (
    <div className="app-container">
      <header>
        <h1>Mykare Health Agent</h1>
      </header>
      
      <main className={`call-interface ${token ? 'video-active' : ''}`}>
        {status === 'Summary' ? (
          <>
            <SummaryPanel data={summaryData} error={summaryError} />
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
                audio={false}
                video={false}
                onConnected={handleConnected}
                onDisconnected={handleDisconnected}
                onError={handleError}
              >
                {/* <AgentAvatar /> */}
                <VideoCallAvatar />
                <AgentTracker onAgentJoined={handleAgentJoined} />
                <RoomAudioRenderer />
                <ActiveCallInterface />
                
                {/* Fallback Controls */}
                <div className="call-controls-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', margin: '1rem auto 0', zIndex: 50, position: 'relative', width: '100%', maxWidth: '500px' }}>
                   {errorMsg && (
                      <div style={{ background: '#fee2e2', color: '#991b1b', padding: '0.5rem 1rem', borderRadius: '8px', fontSize: '0.9rem', width: '100%', textAlign: 'center' }}>
                        {errorMsg}
                      </div>
                   )}
                   
                   {/* Top Action Row: Mic & End Call */}
                   <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', width: '100%' }}>
                     <TrackToggle source={Track.Source.Microphone} className="mic-toggle-btn" style={{ flexShrink: 0 }}>
                        Mic
                     </TrackToggle>
                     
                     {status === 'Agent joined' && (
                       <button type="button" className="danger-btn" onClick={handleEndCall} style={{ borderRadius: '99px', padding: '0.75rem 1.5rem', fontWeight: 600, border: 'none', cursor: 'pointer' }}>
                         End Call
                       </button>
                     )}
                   </div>
                   
                   {/* Bottom Row: Chat */}
                   <div className="chat-container" style={{ width: '100%', minHeight: '300px' }}>
                     <Chat 
                        messageFormatter={(text) => text}
                     />
                   </div>
                </div>
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

              {status === 'Ready' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center' }}>
                  <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                    The AI agent will ask for your name and phone number.
                  </p>
                  <button 
                    type="button" 
                    className="primary-btn"
                    onClick={handleStartCall}
                  >
                    Start Call
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export default App
