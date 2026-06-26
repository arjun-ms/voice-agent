import { render, screen, fireEvent, act } from '@testing-library/react'
import { vi } from 'vitest'
import App from './App'

const mockUseVoiceAssistant = vi.fn()
const mockUseRemoteParticipants = vi.fn()

vi.mock('@livekit/components-react', () => ({
  LiveKitRoom: ({ children, onConnected }: any) => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const React = require('react')
    React.useEffect(() => {
      if (onConnected) onConnected()
    }, []) // Only run once on mount
    return <div data-testid="livekit-room">{children}</div>
  },
  RoomAudio: () => <div data-testid="room-audio" />,
  RoomAudioRenderer: () => null,
  useDataChannel: vi.fn().mockReturnValue([]),
  useRemoteParticipants: () => mockUseRemoteParticipants(),
  useVoiceAssistant: () => mockUseVoiceAssistant(),
  BarVisualizer: () => <div data-testid="bar-visualizer" />
}))

describe('App Call UI', () => {
  beforeEach(() => {
    mockUseRemoteParticipants.mockReturnValue([])
    mockUseVoiceAssistant.mockReturnValue({ state: 'disconnected' })
    vi.clearAllMocks()
  })

  it('renders initial state with Start Call button and Avatar placeholder', () => {
    render(<App />)
    
    const startButton = screen.getByRole('button', { name: /start call/i })
    expect(startButton).toBeInTheDocument()
    
    const avatar = screen.getByTestId('avatar-placeholder')
    expect(avatar).toBeInTheDocument()
    
    const status = screen.getByText(/ready/i)
    expect(status).toBeInTheDocument()
  })

  it('changes state to Connecting when Start Call is clicked', () => {
    render(<App />)
    const startButton = screen.getByRole('button', { name: /start call/i })
    fireEvent.click(startButton)
    
    expect(screen.getByText(/connecting/i)).toBeInTheDocument()
  })

  it('fetches token and changes state to Waiting for agent, then AgentAvatar shows Initializing', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ token: 'mock-token' })
    })

    const { rerender } = render(<App />)
    const startButton = screen.getByRole('button', { name: /start call/i })
    fireEvent.click(startButton)

    expect(await screen.findByText(/Waiting for agent/i)).toBeInTheDocument()

    // Simulate agent joining
    mockUseRemoteParticipants.mockReturnValue([{ identity: 'agent' }])
    mockUseVoiceAssistant.mockReturnValue({ state: 'initializing' })
    rerender(<App />)
    
    const endButton = await screen.findByRole('button', { name: /end call/i })
    expect(endButton).toBeInTheDocument()
    
    // Status should be Initializing... from AgentAvatar
    expect(screen.getByText(/Initializing.../i)).toBeInTheDocument()
    // "Agent joined" is not visible anymore, we just know it's joined because the end call button is visible.

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/token', expect.objectContaining({
      method: 'POST'
    }))
  })

  it('changes state back to Ready when End Call is clicked', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ token: 'mock-token' })
    })

    const { rerender } = render(<App />)

    fireEvent.click(screen.getByText('Start Call'))
    
    expect(await screen.findByText(/Waiting for agent/i)).toBeInTheDocument()

    // Simulate agent joining
    mockUseRemoteParticipants.mockReturnValue([{ identity: 'agent' }])
    mockUseVoiceAssistant.mockReturnValue({ state: 'speaking' })
    rerender(<App />)
    
    const endButton = await screen.findByRole('button', { name: /end call/i })
    fireEvent.click(endButton)

    const newCallBtn = await screen.findByRole('button', { name: /start new call/i })
    fireEvent.click(newCallBtn)

    expect(await screen.findByRole('button', { name: /start call/i })).toBeInTheDocument()
    expect(screen.queryByTestId('livekit-room')).not.toBeInTheDocument()
  })

  it('fetches and displays summary after call ends', async () => {
    const mockSummary = {
      summary: 'Test summary from backend',
      appointments: [],
      preferences: 'None',
      timestamp: '2026-06-26 10:00:00'
    }

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/token')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ token: 'mock-token', room_name: 'room-1', server_url: 'ws://mock-server' })
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockSummary)
      })
    })

    const { rerender } = render(<App />)

    fireEvent.click(screen.getByText('Start Call'))
    
    expect(await screen.findByText(/Waiting for agent/i)).toBeInTheDocument()

    // Simulate agent joining
    mockUseRemoteParticipants.mockReturnValue([{ identity: 'agent' }])
    mockUseVoiceAssistant.mockReturnValue({ state: 'listening' })
    rerender(<App />)
    
    expect(await screen.findByText('Listening...')).toBeInTheDocument()

    fireEvent.click(screen.getByText('End Call'))
    
    expect(await screen.findByText(/Generating summary|Conversation Summary/i)).toBeInTheDocument()
    
    expect(await screen.findByText('Test summary from backend', {}, { timeout: 4000 })).toBeInTheDocument()
    
    const startNewBtn = await screen.findByText('Start New Call')
    fireEvent.click(startNewBtn)
    
    expect(screen.getByText('Ready')).toBeInTheDocument()
  })
})
