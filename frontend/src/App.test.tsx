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

// Helper: mock fetch that handles /health and /token
function mockFetchHealthy(overrides?: Record<string, any>) {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/health')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
    }
    if (url.includes('/token')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ token: 'mock-token', room_name: 'room-1', server_url: 'ws://mock', ...overrides })
      })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  })
}

describe('App Call UI', () => {
  beforeEach(() => {
    mockUseRemoteParticipants.mockReturnValue([])
    mockUseVoiceAssistant.mockReturnValue({ state: 'disconnected' })
    vi.clearAllMocks()
    vi.useRealTimers()
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
    global.fetch = mockFetchHealthy()
    render(<App />)
    const startButton = screen.getByRole('button', { name: /start call/i })
    fireEvent.click(startButton)
    
    expect(screen.getByText(/connecting/i)).toBeInTheDocument()
  })

  it('fetches token and changes state to Waiting for agent, then AgentAvatar shows Initializing', async () => {
    global.fetch = mockFetchHealthy()

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

    // Health was called, then token
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/health', expect.objectContaining({ method: 'GET' }))
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/token', expect.objectContaining({ method: 'POST' }))
  })

  it('changes state back to Ready when End Call is clicked', async () => {
    global.fetch = mockFetchHealthy()

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

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/health')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
      }
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

  it('pings /health before calling /token to wake up server', async () => {
    const callOrder: string[] = []
    
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/health')) {
        callOrder.push('health')
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
      }
      if (url.includes('/token')) {
        callOrder.push('token')
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ token: 'mock-token', room_name: 'room-1', server_url: 'ws://mock' })
        })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    })

    render(<App />)
    fireEvent.click(screen.getByText('Start Call'))

    await screen.findByText(/Waiting for agent/i)

    // Health was called before token
    expect(callOrder[0]).toBe('health')
    expect(callOrder[1]).toBe('token')
  })

  it('retries /health and shows waking up status on cold start', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let healthCallCount = 0

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/health')) {
        healthCallCount++
        if (healthCallCount <= 2) {
          return Promise.reject(new Error('net::ERR_FAILED'))
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
      }
      if (url.includes('/token')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ token: 'mock-token', room_name: 'room-1', server_url: 'ws://mock' })
        })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    })

    render(<App />)
    
    await act(async () => {
      fireEvent.click(screen.getByText('Start Call'))
    })

    // First health call fails, status changes to waking up
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100)
    })
    expect(screen.getByText(/Waking up server/i)).toBeInTheDocument()

    // Advance through retries
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3100)
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3100)
    })

    // Eventually connects
    await screen.findByText(/Waiting for agent|Connecting/i)
    expect(healthCallCount).toBeGreaterThanOrEqual(3)

    vi.useRealTimers()
  })
})
