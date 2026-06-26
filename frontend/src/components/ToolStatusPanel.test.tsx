import { render, screen } from '@testing-library/react'
import ToolStatusPanel from './ToolStatusPanel'

describe('ToolStatusPanel', () => {
  it('renders nothing when there are no events', () => {
    const { container } = render(<ToolStatusPanel events={[]} />)
    expect(container.firstChild).toBeEmptyDOMElement()
  })

  it('renders a running tool with a spinner and human-readable text', () => {
    const events = [{
      id: '1',
      tool: 'fetch_slots',
      status: 'running'
    }]
    render(<ToolStatusPanel events={events} />)
    
    // Should show human-readable text instead of 'fetch_slots'
    expect(screen.getByText(/Fetching slots/i)).toBeInTheDocument()
    
    // Should have a running indicator
    expect(screen.getByTestId('running-indicator-1')).toBeInTheDocument()
  })

  it('renders a success tool with a checkmark', () => {
    const events = [{
      id: '2',
      tool: 'book_appointment',
      status: 'success',
      result: 'Appointment booked'
    }]
    render(<ToolStatusPanel events={events} />)
    
    expect(screen.getByText(/Booking appointment/i)).toBeInTheDocument()
    expect(screen.getByTestId('success-indicator-2')).toBeInTheDocument()
  })
  
  it('renders an error tool with a cross', () => {
    const events = [{
      id: '3',
      tool: 'identify_user',
      status: 'error',
      result: 'Invalid phone number'
    }]
    render(<ToolStatusPanel events={events} />)
    
    expect(screen.getByText(/Identifying user/i)).toBeInTheDocument()
    expect(screen.getByTestId('error-indicator-3')).toBeInTheDocument()
  })
})
