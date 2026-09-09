/**
 * WebSocket helper for real-time game communications.
 */
export class GameSocket {
  constructor(roomCode, playerId, onMessage, onClose) {
    this.roomCode = roomCode
    this.playerId = playerId
    this.onMessage = onMessage
    this.onClose = onClose
    this.ws = null
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    // During dev with Vite, connects via proxy or directly to port 8000
    const host = window.location.port === '5173' ? '127.0.0.1:8000' : window.location.host
    const wsUrl = `${protocol}//${host}/ws/rooms/${this.roomCode}/${this.playerId}`

    this.ws = new WebSocket(wsUrl)

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (this.onMessage) {
          this.onMessage(payload)
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err)
      }
    }

    this.ws.onclose = (event) => {
      console.warn('WebSocket closed:', event)
      if (this.onClose) {
        this.onClose(event)
      }
    }

    this.ws.onerror = (err) => {
      console.error('WebSocket error:', err)
    }
  }

  send(action, data = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, ...data }))
    } else {
      console.warn('WebSocket is not open. Cannot send:', action)
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}

