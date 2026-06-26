import { useState } from 'react'
import { LiveKitRoom, RoomAudio } from '@livekit/components-react'
import '@livekit/components-styles'
import ActiveCallInterface from './components/ActiveCallInterface'
import './App.css'

function App() {
  const [status, setStatus] = useState('Ready')
  const [token, setToken] = useState('')

  const handleStartCall = async () => {
    setStatus('Connecting...')
    try {
      const response = await fetch('http://localhost:8000/token')
      const data = await response.json()
      if (data.access_token) {
        setToken(data.access_token)
        setStatus('Connected')
      }
    } catch (e) {
      setStatus('Ready')
      console.error('Failed to start call', e)
    }
  }

  const handleEndCall = () => {
    setStatus('Ready')
    setToken('')
  }

  return (
    <div className="app-container">
      <header>
        <h1>Mykare Health Agent</h1>
      </header>
      
      <main className="call-interface">
        <div data-testid="avatar-placeholder" className="avatar-placeholder">
          {/* Will be replaced with real avatar in #11 */}
        </div>
        
        <div className="status-text">
          {status}
        </div>
        
        <div className="controls">
          {status === 'Connected' ? (
            <button type="button" className="danger-btn" onClick={handleEndCall}>
              End Call
            </button>
          ) : (
            <button 
              type="button" 
              className="primary-btn"
              onClick={handleStartCall}
              disabled={status !== 'Ready'}
            >
              Start Call
            </button>
          )}
        </div>

        {token && (
          <LiveKitRoom
            serverUrl="ws://localhost:7880"
            token={token}
            connect={true}
            audio={true}
            video={false}
            onDisconnected={handleEndCall}
          >
            <RoomAudio rendererVolume={1.0} />
            <ActiveCallInterface />
          </LiveKitRoom>
        )}
      </main>
    </div>
  )
}

export default App



