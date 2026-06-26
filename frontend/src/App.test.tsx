import { render, screen, fireEvent } from '@testing-library/react'
import { vi } from 'vitest'
import App from './App'

vi.mock('@livekit/components-react', () => ({
  LiveKitRoom: ({ children }: any) => <div data-testid="livekit-room">{children}</div>,
  RoomAudio: () => <div data-testid="room-audio" />,
  useDataChannel: vi.fn().mockReturnValue([])
}))

describe('App Call UI', () => {
  it('renders initial state with Start Call button and Avatar', () => {
    render(<App />)
    
    // Check for Start Call button
    const startButton = screen.getByRole('button', { name: /start call/i })
    expect(startButton).toBeInTheDocument()
    
    // Check for Avatar placeholder
    const avatar = screen.getByTestId('avatar-placeholder')
    expect(avatar).toBeInTheDocument()
    
    // Check state text
    const status = screen.getByText(/ready/i)
    expect(status).toBeInTheDocument()
  })

  it('changes state to Connecting when Start Call is clicked', () => {
    render(<App />)
    const startButton = screen.getByRole('button', { name: /start call/i })
    fireEvent.click(startButton)
    
    // Status text should change
    expect(screen.getByText(/connecting/i)).toBeInTheDocument()
    
    // Button should be disabled
    expect(startButton).toBeDisabled()
  })

  it('fetches token and changes state to Connected', async () => {
    // Mock global fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ access_token: 'mock-token' })
    })

    render(<App />)
    const startButton = screen.getByRole('button', { name: /start call/i })
    fireEvent.click(startButton)

    // Wait for the token fetch to resolve and the UI to update
    const endButton = await screen.findByRole('button', { name: /end call/i })
    expect(endButton).toBeInTheDocument()
    expect(screen.getByText(/connected/i)).toBeInTheDocument()

    // The fetch should have been called
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/token')
  })

  it('changes state back to Ready when End Call is clicked', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ access_token: 'mock-token' })
    })

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /start call/i }))

    // Wait for connect
    const endButton = await screen.findByRole('button', { name: /end call/i })
    
    // Click End Call
    fireEvent.click(endButton)

    // Should return to ready state
    expect(await screen.findByRole('button', { name: /start call/i })).toBeInTheDocument()
    expect(screen.getByText(/ready/i)).toBeInTheDocument()
  })
})



