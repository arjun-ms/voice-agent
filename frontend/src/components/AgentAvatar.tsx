import { useVoiceAssistant, BarVisualizer } from '@livekit/components-react'

export default function AgentAvatar() {
  const { state, audioTrack } = useVoiceAssistant()

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
        {state === 'speaking' && audioTrack && (
          <BarVisualizer state={state} trackRef={audioTrack} barCount={5} options={{ minHeight: 10 }} />
        )}
      </div>
      <div className="agent-state-badge">
        {getStateDisplay()}
      </div>
    </div>
  )
}
