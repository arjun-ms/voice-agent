import './SummaryPanel.css'

export interface SummaryData {
  summary: string
  appointments: any[]
  preferences: string
  timestamp: string
  cost_breakdown?: {
    duration_minutes: number
    stt_deepgram: string
    tts_cartesia: string
    llm_gemini: string
    total_cost: string
  }
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

      {data.cost_breakdown && (
        <div className="summary-section cost-breakdown">
          <h3>Approximate Call Cost</h3>
          <ul>
            <li><strong>Duration:</strong> {data.cost_breakdown.duration_minutes} mins</li>
            <li><strong>Deepgram (STT):</strong> {data.cost_breakdown.stt_deepgram}</li>
            <li><strong>Cartesia (TTS):</strong> {data.cost_breakdown.tts_cartesia}</li>
            <li><strong>Gemini 1.5 (LLM):</strong> {data.cost_breakdown.llm_gemini}</li>
            <li className="total-cost"><strong>Total Estimated Cost:</strong> {data.cost_breakdown.total_cost}</li>
          </ul>
        </div>
      )}

      <div className="summary-footer">
        <small>Generated at: {data.timestamp}</small>
      </div>
    </div>
  )
}
