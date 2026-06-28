import { useVoiceAssistant, BarVisualizer, useTracks, VideoTrack } from '@livekit/components-react'
import { Track } from 'livekit-client'

export default function VideoCallAvatar() {
  const { state, audioTrack } = useVoiceAssistant()
  
  // Find a video track from the remote participant (agent)
  const tracks = useTracks([Track.Source.Camera])
  const videoTrack = tracks.length > 0 ? tracks[0] : null

  const getStateDisplay = () => {
    switch (state) {
      case 'initializing':
        return 'Connecting to Agent...'
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
    <div className={`video-call-container ${state}`}>
      {/* Loading State Overlay */}
      {state === 'initializing' && (
        <div className="video-loading-overlay">
          <div className="spinner"></div>
          <p>Connecting to Anna...</p>
        </div>
      )}
      
      {/* Video Track or Fallback */}
      {videoTrack ? (
        <VideoTrack trackRef={videoTrack} className="full-screen-video" />
      ) : (
        <div className="video-fallback">
          <div className="avatar-placeholder-large">
            {/* If no video, we still show the visualizer inside the placeholder if speaking */}
          </div>
          {state === 'speaking' && audioTrack && (
             <div className="audio-visualizer-overlay">
                <BarVisualizer state={state} trackRef={audioTrack} barCount={7} options={{ minHeight: 15 }} />
             </div>
          )}
        </div>
      )}

      {/* Status Overlay Badge in Top Left */}
      <div className="video-status-overlay">
        <span className={`status-indicator ${state}`}></span>
        {getStateDisplay()}
      </div>
    </div>
  )
}
