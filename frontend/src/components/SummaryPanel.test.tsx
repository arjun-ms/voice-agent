import { render, screen } from '@testing-library/react'
import SummaryPanel from './SummaryPanel'

describe('SummaryPanel', () => {
  it('renders a loading state when data is null', () => {
    render(<SummaryPanel data={null} />)
    expect(screen.getByText(/Generating summary/i)).toBeInTheDocument()
  })

  it('renders structured summary data', () => {
    const mockData = {
      summary: 'Patient called to book a dentist appointment.',
      appointments: [
        { date: '2026-06-30', time: '10:00 AM', status: 'booked' }
      ],
      preferences: 'Prefers morning slots.',
      timestamp: '2026-06-26 10:00:00'
    }

    render(<SummaryPanel data={mockData} />)

    expect(screen.getByText('Patient called to book a dentist appointment.')).toBeInTheDocument()
    expect(screen.getByText('2026-06-30')).toBeInTheDocument()
    expect(screen.getByText('10:00 AM')).toBeInTheDocument()
    expect(screen.getByText('Prefers morning slots.')).toBeInTheDocument()
    expect(screen.getByText(/2026-06-26 10:00:00/)).toBeInTheDocument()
  })
})
