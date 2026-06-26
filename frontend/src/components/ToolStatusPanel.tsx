import './ToolStatusPanel.css'

export type ToolStatus = 'running' | 'success' | 'error'

export interface ToolEvent {
  id: string
  tool: string
  status: ToolStatus
  result?: string
}

interface ToolStatusPanelProps {
  events: ToolEvent[]
}

const getHumanReadableToolName = (tool: string): string => {
  const map: Record<string, string> = {
    identify_user: 'Identifying user...',
    fetch_slots: 'Fetching slots...',
    book_appointment: 'Booking appointment...',
    retrieve_appointments: 'Retrieving appointments...',
    cancel_appointment: 'Canceling appointment...',
    modify_appointment: 'Modifying appointment...',
    end_conversation: 'Ending conversation...'
  }
  return map[tool] || tool
}

export default function ToolStatusPanel({ events }: ToolStatusPanelProps) {
  if (!events || events.length === 0) {
    return <div className="tool-status-panel-empty"></div>
  }

  return (
    <div className="tool-status-panel">
      {events.map((evt) => (
        <div key={evt.id} className={`tool-event tool-event-${evt.status}`}>
          <div className="tool-event-header">
            {evt.status === 'running' && (
              <span data-testid={`running-indicator-${evt.id}`} className="indicator running-indicator">↻</span>
            )}
            {evt.status === 'success' && (
              <span data-testid={`success-indicator-${evt.id}`} className="indicator success-indicator">✓</span>
            )}
            {evt.status === 'error' && (
              <span data-testid={`error-indicator-${evt.id}`} className="indicator error-indicator">✗</span>
            )}
            <span className="tool-name">{getHumanReadableToolName(evt.tool)}</span>
          </div>
          {evt.result && <div className="tool-result">{evt.result}</div>}
        </div>
      ))}
    </div>
  )
}
