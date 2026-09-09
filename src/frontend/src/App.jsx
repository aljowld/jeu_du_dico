import { useState } from 'react'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import './App.css'
import { useEffect, useRef, useState } from 'react'
import { GameSocket } from './socket'

function App() {
  const [count, setCount] = useState(0)
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

  // In-game local inputs
  const [fakeDefinition, setFakeDefinition] = useState('')
  const [selectedVoteId, setSelectedVoteId] = useState(null)

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

  // Reset inputs when game phase changes
  useEffect(() => {
    if (gameState?.state === 'WRITING') {
      setFakeDefinition('')
    }
    if (gameState?.state === 'VOTING') {
      setSelectedVoteId(null)
    }
  }, [gameState?.state])

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

  const handleSubmitDefinition = (e) => {
    e.preventDefault()
    if (!fakeDefinition.trim()) return
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

  return (
    <>
      <section id="center">
        <div className="hero">
          <img src={heroImg} className="base" width="170" height="179" alt="" />
          <img src={reactLogo} className="framework" alt="React logo" />
          <img src={viteLogo} className="vite" alt="Vite logo" />
    <div className="app-container">
      <header className="app-header">
        <div className="brand">📖 Le Jeu du Dico</div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <span className="room-badge">SALLE : {player.room_code}</span>
        </div>
        <div>
          <h1>Get started</h1>
          <p>
            Edit <code>src/App.jsx</code> and save to test <code>HMR</code>
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

          <div>
            <h3>Joueurs connectés ({gameState?.players?.length || 0}) :</h3>
            <div className="player-list" style={{ marginTop: '12px' }}>
              {gameState?.players?.map((p) => (
                <div key={p.id} className={`player-chip ${p.is_host ? 'host' : ''}`}>
                  <span>{p.name}</span>
                  {p.is_host && <span>👑</span>}
                </div>
              ))}
            </div>
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
        </div>
      )}

      {/* --- WORD SELECTION (REROLL OPTION) --- */}
      {gameState?.state === 'WORD_SELECTION' && (
        <div className="card" style={{ textAlign: 'center' }}>
          <p style={{ color: 'var(--text-secondary)' }}>Manche {gameState.round_number} - Le mot mystère est :</p>
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
        <button
          type="button"
          className="counter"
          onClick={() => setCount((count) => count + 1)}
        >
          Count is {count}
        </button>
      </section>
      )}

      <div className="ticks"></div>
      {/* --- WRITING PHASE --- */}
      {gameState?.state === 'WRITING' && (
        <div className="card">
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: 'var(--text-secondary)' }}>Mot à définir :</p>
            <div className="word-display" style={{ fontSize: '2rem', margin: '8px 0' }}>
              {gameState.current_word}
            </div>
          </div>

      <section id="next-steps">
        <div id="docs">
          <svg className="icon" role="presentation" aria-hidden="true">
            <use href="/icons.svg#documentation-icon"></use>
          </svg>
          <h2>Documentation</h2>
          <p>Your questions, answered</p>
          <ul>
            <li>
              <a href="https://vite.dev/" target="_blank">
                <img className="logo" src={viteLogo} alt="" />
                Explore Vite
              </a>
            </li>
            <li>
              <a href="https://react.dev/" target="_blank">
                <img className="button-icon" src={reactLogo} alt="" />
                Learn more
              </a>
            </li>
          </ul>
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
        <div id="social">
          <svg className="icon" role="presentation" aria-hidden="true">
            <use href="/icons.svg#social-icon"></use>
          </svg>
          <h2>Connect with us</h2>
          <p>Join the Vite community</p>
          <ul>
            <li>
              <a href="https://github.com/vitejs/vite" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
      )}

      {/* --- VOTING PHASE --- */}
      {gameState?.state === 'VOTING' && (
        <div className="card">
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: 'var(--text-secondary)' }}>Trouve la VRAIE définition pour :</p>
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
                  <use href="/icons.svg#github-icon"></use>
                </svg>
                GitHub
              </a>
            </li>
            <li>
              <a href="https://chat.vite.dev/" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#discord-icon"></use>
                </svg>
                Discord
              </a>
            </li>
            <li>
              <a href="https://x.com/vite_js" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#x-icon"></use>
                </svg>
                X.com
              </a>
            </li>
            <li>
              <a href="https://bsky.app/profile/vite.dev" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#bluesky-icon"></use>
                </svg>
                Bluesky
              </a>
            </li>
          </ul>
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
      </section>
      )}

      <div className="ticks"></div>
      <section id="spacer"></section>
    </>
      {/* --- REVEAL PHASE --- */}
      {gameState?.state === 'REVEAL' && (
        <div className="card">
          <div style={{ textAlign: 'center' }}>
            <h2>Résultats de la manche 🏆</h2>
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
              Manche suivante ➡️
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default App
