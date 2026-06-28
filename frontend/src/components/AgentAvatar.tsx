import { useVoiceAssistant, BarVisualizer, useTracks, VideoTrack } from '@livekit/components-react'
import { Track } from 'livekit-client'

export default function AgentAvatar() {
  const { state, audioTrack } = useVoiceAssistant()
  
  // Find a video track from the remote participant (agent)
  const tracks = useTracks([Track.Source.Camera])
  const videoTrack = tracks.length > 0 ? tracks[0] : null

  const getStateDisplay = () => {
    switch (state) {
      case 'initializing':
        return 'Initializing...'
      case 'listening':
        return 'Listening...'
      case 'thinking':
        return 'Thinking...'
      case 'speaking':
        return 'Speaking...'
      case 'disconnected':
      default:
        return 'Disconnected'
    }
  }

  return (
    <div className={`agent-avatar-container ${state}`}>
      <div className="avatar-circle">
        {state === 'initializing' && <div className="spinner avatar-spinner" data-testid="avatar-spinner"></div>}
        
        {videoTrack ? (
          <VideoTrack trackRef={videoTrack} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
        ) : (
          state === 'speaking' && audioTrack && (
            <BarVisualizer state={state} trackRef={audioTrack} barCount={5} options={{ minHeight: 10 }} />
          )
        )}
      </div>
      <div className="agent-state-badge">
        {getStateDisplay()}
      </div>
    </div>
  )
}
