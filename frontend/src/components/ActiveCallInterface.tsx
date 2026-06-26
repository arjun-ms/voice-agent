import React, { useState } from 'react'
import { useDataChannel } from '@livekit/components-react'
import ToolStatusPanel, { ToolEvent } from './ToolStatusPanel'

export default function ActiveCallInterface() {
  const [events, setEvents] = useState<ToolEvent[]>([])

  useDataChannel('reliable', (msg) => {
    try {
      const payload = JSON.parse(new TextDecoder().decode(msg.payload))
      if (payload.tool && payload.status) {
        setEvents((prev) => {
          // If running, add new. If success/error, update existing running tool of same name.
          if (payload.status === 'running') {
            return [...prev, { id: Date.now().toString(), tool: payload.tool, status: 'running' }]
          } else {
            const newEvents = [...prev]
            // find last running event of this tool
            for (let i = newEvents.length - 1; i >= 0; i--) {
              if (newEvents[i].tool === payload.tool && newEvents[i].status === 'running') {
                newEvents[i] = { ...newEvents[i], status: payload.status, result: payload.result }
                break
              }
            }
            return newEvents
          }
        })
      }
    } catch (e) {
      console.error('Failed to parse data message', e)
    }
  })

  return (
    <div className="active-call">
      <ToolStatusPanel events={events} />
    </div>
  )
}
