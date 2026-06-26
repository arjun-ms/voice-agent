import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import AgentAvatar from './AgentAvatar'
import * as livekitComponents from '@livekit/components-react'

vi.mock('@livekit/components-react', () => ({
  useVoiceAssistant: vi.fn(),
  BarVisualizer: () => <div data-testid="bar-visualizer" />
}))

describe('AgentAvatar', () => {
  it('renders disconnected state', () => {
    vi.spyOn(livekitComponents, 'useVoiceAssistant').mockReturnValue({
      state: 'disconnected',
      audioTrack: undefined
    } as any)
    
    render(<AgentAvatar />)
    expect(screen.getByText('Disconnected')).toBeInTheDocument()
  })

  it('renders initializing state with a spinner', () => {
    vi.spyOn(livekitComponents, 'useVoiceAssistant').mockReturnValue({
      state: 'initializing',
      audioTrack: undefined
    } as any)
    
    render(<AgentAvatar />)
    expect(screen.getByText('Initializing...')).toBeInTheDocument()
    expect(screen.getByTestId('avatar-spinner')).toBeInTheDocument()
  })

  it('renders listening state', () => {
    vi.spyOn(livekitComponents, 'useVoiceAssistant').mockReturnValue({
      state: 'listening',
      audioTrack: undefined
    } as any)
    
    render(<AgentAvatar />)
    expect(screen.getByText('Listening...')).toBeInTheDocument()
  })

  it('renders thinking state', () => {
    vi.spyOn(livekitComponents, 'useVoiceAssistant').mockReturnValue({
      state: 'thinking',
      audioTrack: undefined
    } as any)
    
    render(<AgentAvatar />)
    expect(screen.getByText('Thinking...')).toBeInTheDocument()
  })

  it('renders speaking state and shows audio visualizer', () => {
    vi.spyOn(livekitComponents, 'useVoiceAssistant').mockReturnValue({
      state: 'speaking',
      audioTrack: { sid: 'track-1' }
    } as any)
    
    render(<AgentAvatar />)
    expect(screen.getByText('Speaking...')).toBeInTheDocument()
    expect(screen.getByTestId('bar-visualizer')).toBeInTheDocument()
  })
})
