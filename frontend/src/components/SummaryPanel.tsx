import './SummaryPanel.css'

export interface SummaryData {
  summary: string
  appointments: any[]
  preferences: string
  timestamp: string
}

interface SummaryPanelProps {
  data: SummaryData | null
}

export default function SummaryPanel({ data }: SummaryPanelProps) {
  if (!data) {
    return (
      <div className="summary-panel loading">
        <div className="spinner"></div>
        <p>Generating summary...</p>
      </div>
    )
  }

  return (
    <div className="summary-panel">
      <h2>Conversation Summary</h2>
      
      <div className="summary-section">
        <h3>Summary</h3>
        <p>{data.summary}</p>
      </div>

      <div className="summary-section">
        <h3>Appointments</h3>
        {data.appointments && data.appointments.length > 0 ? (
          <ul className="appointments-list">
            {data.appointments.map((appt, i) => (
              <li key={i} className="appointment-item">
                <span className="appt-date">{appt.date}</span>
                <span className="appt-time">{appt.time}</span>
                <span className="appt-status">{appt.status}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="no-data-text">No upcoming appointments.</p>
        )}
      </div>

      {data.preferences && (
        <div className="summary-section">
          <h3>Preferences</h3>
          <p>{data.preferences}</p>
        </div>
      )}

      <div className="summary-footer">
        <small>Generated at: {data.timestamp}</small>
      </div>
    </div>
  )
}
