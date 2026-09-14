import { useEffect, useRef, useState } from 'react'
import { GameSocket } from './socket'

function formatDuration(totalSeconds) {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  if (m > 0 && s > 0) return `${m} min ${s.toString().padStart(2, '0')} s`
  if (m > 0) return `${m} min`
  return `${s} s`
}

export default function App() {
  // Session & Connection state
  const [player, setPlayer] = useState(null) // { room_code, player_id, player_name, is_host }
  const [gameState, setGameState] = useState(null) // State payload received from server
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Form states for join/create
  const [tab, setTab] = useState('join') // 'join' | 'create'
  const [nickname, setNickname] = useState('')
  const [roomCodeInput, setRoomCodeInput] = useState('')

  // Lobby view state
  const [lobbyTab, setLobbyTab] = useState('players') // 'players' | 'settings'

  // In-game local inputs
  const [fakeDefinition, setFakeDefinition] = useState('')
  const [selectedVoteId, setSelectedVoteId] = useState(null)
  const [timeLeft, setTimeLeft] = useState(null)

  const socketRef = useRef(null)

  // Establish WebSocket connection whenever player is set
  useEffect(() => {
    if (!player) return

    const socket = new GameSocket(
      player.room_code,
      player.player_id,
      (message) => {
        if (message.type === 'STATE_UPDATE') {
          setGameState(message.data)
          if (message.data.players && !message.data.players.some((p) => p.id === player.player_id)) {
            setError('Vous avez été retiré de la partie après une période d\'inactivité.')
            setPlayer(null)
            setGameState(null)
          }
        }
      },
      () => {
        setError('Connexion perdue avec le serveur de jeu.')
      }
    )

    socket.connect()
    socketRef.current = socket

    return () => {
      socket.disconnect()
    }
  }, [player])

  // Keep latest input in a ref for auto-submission on timer expiration
  const fakeDefinitionRef = useRef(fakeDefinition)
  useEffect(() => {
    fakeDefinitionRef.current = fakeDefinition
  }, [fakeDefinition])

  const hasSubmittedRef = useRef(false)

  // Reset inputs when game phase changes
  useEffect(() => {
    if (gameState?.state === 'WRITING') {
      setFakeDefinition('')
      hasSubmittedRef.current = false
    }
    if (gameState?.state === 'VOTING') {
      setSelectedVoteId(null)
    }
  }, [gameState?.state])

  // Countdown timer for WRITING phase with automatic submission when timer ends
  useEffect(() => {
    if (gameState?.state === 'WRITING' && gameState.writing_started_at && gameState.writing_time_limit) {
      const updateTimer = () => {
        const now = Date.now() / 1000
        const elapsed = now - gameState.writing_started_at
        const remaining = Math.max(0, Math.ceil(gameState.writing_time_limit - elapsed))
        setTimeLeft(remaining)

        // Automatically validate / submit whatever text was entered when timer expires
        if (remaining <= 0 && !hasSubmittedRef.current && !gameState.has_submitted) {
          hasSubmittedRef.current = true
          const textToSubmit = fakeDefinitionRef.current.trim() || '(Aucune proposition)'
          sendAction('SUBMIT_DEFINITION', { definition: textToSubmit })
        }
      }
      updateTimer()
      const interval = setInterval(updateTimer, 250)
      return () => clearInterval(interval)
    }
    setTimeLeft(null)
  }, [gameState?.state, gameState?.writing_started_at, gameState?.writing_time_limit, gameState?.has_submitted])



  // --- Handlers ---
  const handleCreateRoom = async (e) => {
    e.preventDefault()
    if (!nickname.trim()) return
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host_name: nickname.trim() }),
      })
      if (!res.ok) throw new Error('Impossible de créer la salle.')
      const data = await res.json()
      setPlayer(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleJoinRoom = async (e) => {
    e.preventDefault()
    if (!nickname.trim() || !roomCodeInput.trim()) return
    setError('')
    setLoading(true)
    try {
      const code = roomCodeInput.trim().toUpperCase()
      const res = await fetch(`/api/rooms/${code}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_name: nickname.trim() }),
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => null)
        if (errJson?.detail) throw new Error(errJson.detail)
        if (res.status === 404) throw new Error('Salle introuvable avec ce code.')
        throw new Error('Erreur lors de la tentative de rejoindre.')
      }
      const data = await res.json()
      setPlayer(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const sendAction = (action, payload = {}) => {
    if (socketRef.current) {
      socketRef.current.send(action, payload)
    }
  }

  const handleStartGame = () => sendAction('START_GAME')
  const handleReroll = () => sendAction('REROLL_WORD')
  const handleStartWriting = () => sendAction('START_WRITING')
  const handleNextRound = () => sendAction('NEXT_ROUND')

  const handleUpdateWritingTime = (newSeconds) => {
    if (newSeconds >= 10 && newSeconds <= 300) {
      sendAction('UPDATE_SETTINGS', { writing_time_limit: newSeconds })
    }
  }

  const handleUpdateMaxRounds = (newRounds) => {
    if (newRounds >= 1 && newRounds <= 20) {
      sendAction('UPDATE_SETTINGS', { max_rounds: newRounds })
    }
  }

  const handleLeaveRoom = () => {
    if (socketRef.current) {
      socketRef.current.send('LEAVE_ROOM', {})
      socketRef.current.disconnect()
    }
    setPlayer(null)
    setGameState(null)
    setError('')
  }

  const handleSubmitDefinition = (e) => {
    if (e) e.preventDefault()
    if (!fakeDefinition.trim()) return
    hasSubmittedRef.current = true
    sendAction('SUBMIT_DEFINITION', { definition: fakeDefinition.trim() })
  }



  const handleSubmitVote = (optionId) => {
    setSelectedVoteId(optionId)
    sendAction('SUBMIT_VOTE', { option_id: optionId })
  }

  // --- Screens rendering ---

  // 1. Join / Create screen
  if (!player) {
    return (
      <div className="app-container">
        <header className="app-header">
          <div className="brand">📖 Le Jeu du Dico</div>
        </header>

        <div className="card">
          <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--card-border)', paddingBottom: '14px' }}>
            <button
              className={`btn ${tab === 'join' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
              onClick={() => setTab('join')}
            >
              Rejoindre
            </button>
            <button
              className={`btn ${tab === 'create' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
              onClick={() => setTab('create')}
            >
              Créer un salon
            </button>
          </div>

          {error && <div style={{ color: 'var(--error)', fontWeight: 600 }}>⚠️ {error}</div>}

          {tab === 'join' ? (
            <form onSubmit={handleJoinRoom} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="form-group">
                <label>Ton pseudo</label>
                <input
                  type="text"
                  placeholder="Ex: Martin"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  maxLength={30}
                  required
                />
              </div>
              <div className="form-group">
                <label>Code de la salle (4 lettres)</label>
                <input
                  type="text"
                  placeholder="Ex: ABCD"
                  value={roomCodeInput}
                  onChange={(e) => setRoomCodeInput(e.target.value.toUpperCase())}
                  maxLength={4}
                  required
                />
              </div>
              <button type="submit" className="btn btn-accent" disabled={loading}>
                {loading ? 'Connexion...' : 'Entrer dans la partie 🚀'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleCreateRoom} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="form-group">
                <label>Ton pseudo d'hôte</label>
                <input
                  type="text"
                  placeholder="Ex: Jeanne"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  maxLength={30}
                  required
                />
              </div>
              <button type="submit" className="btn btn-accent" disabled={loading}>
                {loading ? 'Création...' : 'Créer la salle 👑'}
              </button>
            </form>
          )}
        </div>
      </div>
    )
  }

  // 2. In-game screens
  const isHost = gameState?.is_host ?? player.is_host
  const writingTimeLimit = gameState?.writing_time_limit ?? 60

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand">📖 Le Jeu du Dico</div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <span className="room-badge">SALLE : {player.room_code}</span>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.85rem' }}
            onClick={handleLeaveRoom}
            title="Quitter la salle"
          >
            🚪 Quitter
          </button>
        </div>
      </header>

      {error && <div style={{ color: 'var(--error)', fontWeight: 600 }}>⚠️ {error}</div>}

      {/* --- LOBBY --- */}
      {gameState?.state === 'LOBBY' && (
        <div className="card">
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: 'var(--text-secondary)' }}>Partage ce code à tes amis :</p>
            <h1 style={{ fontSize: '3.5rem', color: '#fbbf24', letterSpacing: '4px' }}>
              {player.room_code}
            </h1>
          </div>

          {/* Lobby navigation tabs */}
          <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--card-border)', paddingBottom: '12px' }}>
            <button
              className={`btn ${lobbyTab === 'players' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, padding: '10px 16px', fontSize: '1rem' }}
              onClick={() => setLobbyTab('players')}
            >
              👥 Joueurs ({gameState?.players?.length || 0}/{gameState?.max_players || 10})
            </button>
            <button
              className={`btn ${lobbyTab === 'settings' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, padding: '10px 16px', fontSize: '1rem' }}
              onClick={() => setLobbyTab('settings')}
            >
              ⚙️ Paramètres {isHost ? '👑' : ''}
            </button>
          </div>

          {/* Tab 1: Players list */}
          {lobbyTab === 'players' && (
            <>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                    Joueurs dans le salon ({gameState?.players?.length || 0}/{gameState?.max_players || 10})
                  </span>
                  {(gameState?.players?.length || 0) >= (gameState?.max_players || 10) && (
                    <span style={{ fontSize: '0.8rem', color: 'var(--accent)', background: 'rgba(245, 158, 11, 0.15)', padding: '3px 8px', borderRadius: '6px', fontWeight: 600 }}>
                      Salon complet (10 max)
                    </span>
                  )}
                </div>
                <div className="player-list">
                  {gameState?.players?.map((p) => (
                    <div
                      key={p.id}
                      className={`player-chip ${p.is_host ? 'host' : ''}`}
                      style={!p.is_connected ? { opacity: 0.55, borderStyle: 'dashed' } : {}}
                      title={!p.is_connected ? 'Déconnecté (expulsion automatique après 30s)' : ''}
                    >
                      <span>{p.name}</span>
                      {p.is_host && <span>👑</span>}
                      {!p.is_connected && (
                        <span style={{ fontSize: '0.75rem', color: '#f87171', marginLeft: '4px' }}>
                          🔌 Hors-ligne
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Direct timer controls in lobby view */}
              <div style={{
                background: 'rgba(15, 23, 42, 0.5)',
                border: '1px solid var(--card-border)',
                borderRadius: '14px',
                padding: '14px 18px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '12px',
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    ⏱️ Temps d'écriture :
                    <span style={{ color: '#fbbf24', fontFamily: 'var(--font-display)', fontSize: '1.25rem' }}>
                      {formatDuration(writingTimeLimit)}
                    </span>
                  </div>
                </div>

                {isHost && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ width: '40px', height: '40px', fontSize: '1.4rem', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                      disabled={writingTimeLimit <= 10}
                      onClick={() => handleUpdateWritingTime(writingTimeLimit - 5)}
                      title="Diminuer de 5 secondes"
                    >
                      −
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ width: '40px', height: '40px', fontSize: '1.4rem', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                      disabled={writingTimeLimit >= 300}
                      onClick={() => handleUpdateWritingTime(writingTimeLimit + 5)}
                      title="Augmenter de 5 secondes"
                    >
                      +
                    </button>
                  </div>
                )}
              </div>

              <div style={{
                background: 'rgba(15, 23, 42, 0.5)',
                border: '1px solid var(--card-border)',
                borderRadius: '14px',
                padding: '14px 18px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '12px',
                marginTop: '12px',
                marginBottom: '16px',
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    🏁 Nombre de manches :
                    <span style={{ color: '#fbbf24', fontFamily: 'var(--font-display)', fontSize: '1.25rem' }}>
                      {gameState?.max_rounds ?? 5}
                    </span>
                  </div>
                </div>

                {isHost && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ width: '40px', height: '40px', fontSize: '1.4rem', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                      disabled={(gameState?.max_rounds ?? 5) <= 1}
                      onClick={() => handleUpdateMaxRounds((gameState?.max_rounds ?? 5) - 1)}
                      title="Diminuer d'une manche"
                    >
                      −
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ width: '40px', height: '40px', fontSize: '1.4rem', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                      disabled={(gameState?.max_rounds ?? 5) >= 20}
                      onClick={() => handleUpdateMaxRounds((gameState?.max_rounds ?? 5) + 1)}
                      title="Augmenter d'une manche"
                    >
                      +
                    </button>
                  </div>
                )}
              </div>

              {isHost ? (
                <button className="btn btn-accent" onClick={handleStartGame}>
                  Lancer la partie 🚀
                </button>
              ) : (
                <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                  En attente que l'hôte lance la partie...
                </p>
              )}
            </>
          )}

          {/* Tab 2: Settings page */}
          {lobbyTab === 'settings' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '1.15rem' }}>⚙️ Paramètres du salon</h3>
                {isHost ? (
                  <span style={{ fontSize: '0.8rem', color: '#fbbf24', background: 'rgba(251, 191, 36, 0.15)', padding: '4px 10px', borderRadius: '8px', fontWeight: 600 }}>
                    👑 Chef de groupe
                  </span>
                ) : (
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                    Lecture seule (modifiable par le chef)
                  </span>
                )}
              </div>

              <div style={{
                background: 'rgba(15, 23, 42, 0.45)',
                border: '1px solid var(--card-border)',
                borderRadius: '16px',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}>
                <div>
                  <h4 style={{ fontSize: '1.05rem', color: 'var(--text-primary)' }}>
                    ⏱️ Temps pour écrire la définition
                  </h4>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Durée accordée aux joueurs pour inventer et soumettre leur définition.
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '20px', margin: '10px 0' }}>
                  {isHost && (
                    <button
                      className="btn btn-secondary"
                      style={{ width: '48px', height: '48px', fontSize: '1.5rem', padding: 0 }}
                      disabled={writingTimeLimit <= 10}
                      onClick={() => handleUpdateWritingTime(writingTimeLimit - 5)}
                    >
                      −
                    </button>
                  )}

                  <div style={{ textAlign: 'center', minWidth: '150px' }}>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: '2.2rem', fontWeight: 700, color: '#fef08a' }}>
                      {formatDuration(writingTimeLimit)}
                    </div>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      ({writingTimeLimit} secondes)
                    </span>
                  </div>

                  {isHost && (
                    <button
                      className="btn btn-secondary"
                      style={{ width: '48px', height: '48px', fontSize: '1.5rem', padding: 0 }}
                      disabled={writingTimeLimit >= 300}
                      onClick={() => handleUpdateWritingTime(writingTimeLimit + 5)}
                    >
                      +
                    </button>
                  )}
                </div>

                <p style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Minimum 10 s · Maximum 5 min
                </p>
              </div>

              <div style={{
                background: 'rgba(15, 23, 42, 0.45)',
                border: '1px solid var(--card-border)',
                borderRadius: '16px',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}>
                <div>
                  <h4 style={{ fontSize: '1.05rem', color: 'var(--text-primary)' }}>
                    🏁 Nombre de manches
                  </h4>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Détermine la durée de la partie.
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '20px', margin: '10px 0' }}>
                  {isHost && (
                    <button
                      className="btn btn-secondary"
                      style={{ width: '48px', height: '48px', fontSize: '1.5rem', padding: 0 }}
                      disabled={(gameState?.max_rounds ?? 5) <= 1}
                      onClick={() => handleUpdateMaxRounds((gameState?.max_rounds ?? 5) - 1)}
                    >
                      −
                    </button>
                  )}

                  <div style={{ textAlign: 'center', minWidth: '150px' }}>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: '2.2rem', fontWeight: 700, color: '#fef08a' }}>
                      {gameState?.max_rounds ?? 5}
                    </div>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      manches
                    </span>
                  </div>

                  {isHost && (
                    <button
                      className="btn btn-secondary"
                      style={{ width: '48px', height: '48px', fontSize: '1.5rem', padding: 0 }}
                      disabled={(gameState?.max_rounds ?? 5) >= 20}
                      onClick={() => handleUpdateMaxRounds((gameState?.max_rounds ?? 5) + 1)}
                    >
                      +
                    </button>
                  )}
                </div>

                <p style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Minimum 1 · Maximum 20
                </p>
              </div>

              {isHost && (
                <button className="btn btn-accent" onClick={handleStartGame}>
                  Lancer la partie 🚀
                </button>
              )}

              <button
                className="btn btn-secondary"
                style={{ alignSelf: 'center' }}
                onClick={() => setLobbyTab('players')}
              >
                ⬅️ Retour à la liste des joueurs
              </button>
            </div>
          )}
        </div>
      )}

      {/* --- WORD SELECTION (REROLL OPTION) --- */}
      {gameState?.state === 'WORD_SELECTION' && (
        <div className="card" style={{ textAlign: 'center' }}>
          <p style={{ color: 'var(--text-secondary)' }}>Manche {gameState.round_number}/{gameState.max_rounds} - Le mot mystère est :</p>
          <div className="word-display">{gameState.current_word}</div>

          <p style={{ fontSize: '1.05rem', marginTop: '10px' }}>
            Quelqu'un connaît-il déjà ce mot ?
          </p>

          {isHost ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '12px' }}>
              <button className="btn btn-secondary" onClick={handleReroll}>
                🔄 Mot connu ? Relancer un tirage (Reroll)
              </button>
              <button className="btn btn-accent" onClick={handleStartWriting}>
                ✍️ Mot inconnu ! Passer à l'écriture
              </button>
            </div>
          ) : (
            <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic', marginTop: '12px' }}>
              Si vous connaissez ce mot, prévenez l'hôte pour qu'il relance le tirage !
            </p>
          )}
        </div>
      )}

      {/* --- WRITING PHASE --- */}
      {gameState?.state === 'WRITING' && (
        <div className="card">
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: 'var(--text-secondary)' }}>Manche {gameState.round_number}/{gameState.max_rounds} - Mot à définir :</p>
            <div className="word-display" style={{ fontSize: '2rem', margin: '8px 0' }}>
              {gameState.current_word}
            </div>

            {/* Countdown timer */}
            {timeLeft !== null && (
              <div style={{
                fontFamily: 'var(--font-display)',
                fontSize: '1.3rem',
                fontWeight: 700,
                color: timeLeft <= 10 ? 'var(--error)' : 'var(--accent)',
                color: timeLeft <= 5 ? 'var(--error)' : 'var(--accent)',
                marginTop: '4px',
              }}>
                {timeLeft > 0 ? `⏱️ Temps restant : ${timeLeft} s` : '⏱️ Temps écoulé ! Validation automatique...'}
              </div>
            )}
          </div>

          {gameState.has_submitted ? (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <h2 style={{ color: 'var(--success)' }}>✅ Définition envoyée !</h2>
              <p style={{ color: 'var(--text-secondary)', marginTop: '8px' }}>
                En attente des autres joueurs... ({gameState.submissions_count}/{gameState.total_needed})
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmitDefinition} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="form-group">
                <label>Invente la définition la plus crédible possible :</label>
                <textarea
                  placeholder="Rédige une définition qui a l'air authentique..."
                  value={fakeDefinition}
                  onChange={(e) => setFakeDefinition(e.target.value)}
                  maxLength={500}
                  required
                />
              </div>
              <button type="submit" className="btn btn-accent">
                Envoyer ma définition 📤
              </button>
            </form>
          )}
        </div>
      )}

      {/* --- VOTING PHASE --- */}
      {gameState?.state === 'VOTING' && (
        <div className="card">
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: 'var(--text-secondary)' }}>Manche {gameState.round_number}/{gameState.max_rounds} - Trouve la VRAIE définition pour :</p>
            <div className="word-display" style={{ fontSize: '2rem', margin: '8px 0' }}>
              {gameState.current_word}
            </div>
          </div>

          <div className="vote-options">
            {gameState.options?.map((opt) => {
              const isOwn = opt.is_own
              const isSelected = selectedVoteId === opt.id

              return (
                <button
                  key={opt.id}
                  disabled={isOwn || gameState.has_voted}
                  className={`option-card ${isOwn ? 'own' : ''} ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleSubmitVote(opt.id)}
                >
                  <p>{opt.text}</p>
                  {isOwn && (
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontStyle: 'italic', display: 'block', marginTop: '6px' }}>
                      (Votre invention - vous ne pouvez pas voter pour elle)
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {gameState.has_voted && (
            <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
              Vote enregistré ! En attente de tout le monde... ({gameState.votes_count}/{gameState.total_needed})
            </p>
          )}
        </div>
      )}

      {/* --- REVEAL PHASE --- */}
      {gameState?.state === 'REVEAL' && (
        <div className="card">
          <div style={{ textAlign: 'center' }}>
            <h2>Résultats de la manche {gameState.round_number}/{gameState.max_rounds} 🏆</h2>
            <div className="word-display" style={{ fontSize: '2rem', margin: '12px 0' }}>
              {gameState.results?.word}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {gameState.results?.options?.map((opt) => (
              <div key={opt.option_id} className={`reveal-card ${opt.is_real ? 'real' : ''}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="reveal-author">
                    {opt.is_real ? '✨ Vraie définition du Dictionnaire' : `✍️ Auteur : ${opt.author_name}`}
                  </span>
                  {opt.is_real && <span style={{ color: '#10b981', fontWeight: 700 }}>+1 pt par vote</span>}
                </div>
                <p style={{ fontSize: '1.05rem', lineHeight: '1.4' }}>{opt.text}</p>

                {opt.voters?.length > 0 ? (
                  <div className="voters-tag">
                    Ont voté pour cette définition : <strong>{opt.voters.join(', ')}</strong>
                  </div>
                ) : (
                  <div className="voters-tag" style={{ opacity: 0.6 }}>
                    Aucun vote
                  </div>
                )}
              </div>
            ))}
          </div>

          <div style={{ marginTop: '16px' }}>
            <h3>Classement général :</h3>
            <div className="scoreboard" style={{ marginTop: '12px' }}>
              {gameState.results?.scoreboard?.map((p, idx) => (
                <div key={p.id} className="score-row">
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, color: 'var(--text-secondary)' }}>#{idx + 1}</span>
                    <span style={{ fontWeight: 600 }}>{p.name}</span>
                  </div>
                  <span className="score-pts">{p.score} pts</span>
                </div>
              ))}
            </div>
          </div>

          {isHost && (
            <button className="btn btn-accent" onClick={handleNextRound} style={{ marginTop: '16px' }}>
              {gameState.round_number >= (gameState.max_rounds ?? 5) ? 'Terminer la partie 🏁' : 'Manche suivante ➡️'}
            </button>
          )}
        </div>
      )}

      {/* --- GAME OVER PHASE --- */}
      {gameState?.state === 'GAME_OVER' && (
        <div className="card">
          <div style={{ textAlign: 'center' }}>
            <h2 style={{ fontSize: '2.5rem', color: '#fbbf24', marginBottom: '16px' }}>Fin de la partie ! 🏁</h2>
            <p style={{ color: 'var(--text-secondary)' }}>Classement final après {gameState.max_rounds} manches</p>
          </div>

          <div className="scoreboard" style={{ marginTop: '24px', padding: '16px', background: 'rgba(15, 23, 42, 0.45)', borderRadius: '16px' }}>
            {gameState.results?.scoreboard?.map((p, idx) => (
              <div key={p.id} className="score-row" style={idx === 0 ? { background: 'rgba(251, 191, 36, 0.15)', borderColor: '#fbbf24', transform: 'scale(1.02)' } : {}}>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, color: idx === 0 ? '#fbbf24' : 'var(--text-secondary)', fontSize: idx === 0 ? '1.2rem' : '1rem' }}>
                    {idx === 0 ? '👑 #1' : `#${idx + 1}`}
                  </span>
                  <span style={{ fontWeight: 600, fontSize: idx === 0 ? '1.2rem' : '1rem' }}>{p.name}</span>
                </div>
                <span className="score-pts" style={idx === 0 ? { color: '#fbbf24', fontSize: '1.2rem' } : {}}>{p.score} pts</span>
              </div>
            ))}
          </div>

          {isHost && (
            <button className="btn btn-primary" onClick={() => sendAction('RETURN_TO_LOBBY')} style={{ marginTop: '24px', width: '100%' }}>
              Retourner au salon 🏠
            </button>
          )}
        </div>
      )}

      <footer style={{ textAlign: 'center', marginTop: '32px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
        Définitions issues du{' '}
        <a
          href="https://fr.wiktionary.org"
          target="_blank"
          rel="noreferrer"
          style={{ color: 'var(--accent)', textDecoration: 'none' }}
        >
          Wiktionnaire
        </a>{' '}
        (licence CC BY-SA 4.0)
      </footer>
    </div>
  )
}
