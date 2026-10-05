import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Volume2,
  Loader2,
  Clock,
  Play,
  Pause,
  AlertTriangle,
  BookOpen,
} from 'lucide-react';
import { fetchBook, fetchBookChunks } from '../api';
import { usePlayer } from '../hooks/usePlayer';
import AudioPlayerBar from '../components/AudioPlayerBar';
import ErrorMessageBox from '../components/ErrorMessageBox';

const POLLING_INTERVAL_MS = 2000;

/**
 * Player Page (/book/:id)
 * Renders ordered storybook sentence chunks with real-time audio sync,
 * auto-scroll, background generation polling, and docked audio controls.
 */
export default function PlayerPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [book, setBook] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);

  // Custom player hook managing audio, preloading, MediaSession, and persistence
  const player = usePlayer(id, book, chunks);
  const { activeChunkIndex, isPlaying, playChunk, pause } = player;

  const activeChunkCardRef = useRef(null);

  // 1. Initial data fetch and background generation polling
  useEffect(() => {
    if (!id) return;

    let isMounted = true;

    async function loadData() {
      try {
        const [bookData, chunksData] = await Promise.all([
          fetchBook(id),
          fetchBookChunks(id),
        ]);

        if (!isMounted) return 'stop';

        setBook(bookData);
        setChunks(chunksData || []);

        // Stop polling if complete or error
        if (bookData.status === 'ready' || bookData.status === 'failed') {
          return 'stop';
        }
        return 'continue';
      } catch (err) {
        if (!isMounted) return 'stop';
        setErrorMessage(err.message || `Failed to load book '${id}'.`);
        return 'stop';
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadData();

    // Poll every 2 seconds if generating
    const intervalId = setInterval(async () => {
      const decision = await loadData();
      if (decision === 'stop') {
        clearInterval(intervalId);
      }
    }, POLLING_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [id]);

  // 2. Auto-scroll active chunk into view smoothly
  useEffect(() => {
    if (activeChunkCardRef.current) {
      activeChunkCardRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [activeChunkIndex]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 20px', color: 'var(--text-muted)' }}>
        <Loader2 size={36} style={{ animation: 'spin 1.2s linear infinite', margin: '0 auto 16px', display: 'block', color: 'var(--accent-primary)' }} />
        <h3 style={{ fontSize: '1.25rem', color: 'var(--text-primary)' }}>Opening Audiobook...</h3>
      </div>
    );
  }

  if (errorMessage && !book) {
    return (
      <div style={{ maxWidth: '680px', margin: '60px auto', padding: '0 20px' }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => navigate('/')}
          style={{ marginBottom: '20px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          <ArrowLeft size={16} /> Back to Library
        </button>
        <ErrorMessageBox error={errorMessage} />
      </div>
    );
  }

  const isBangla = book?.language === 'bn';
  const totalChunks = book?.total_chunks || chunks.length;
  const doneChunks = book?.done_chunks || chunks.filter((c) => c.status === 'done').length;
  const progressPercent = totalChunks > 0 ? Math.round((doneChunks / totalChunks) * 100) : 0;
  const isGenerating = book?.status === 'generating' || book?.status === 'extracting';

  return (
    <div
      className="player-page-container"
      data-lang={book?.language || 'en'}
      style={{ padding: '24px 20px 140px', maxWidth: '960px', margin: '0 auto' }}
    >
      {/* Top Navigation */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => navigate('/')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 16px', fontSize: '0.9rem' }}
        >
          <ArrowLeft size={16} />
          Library
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className={`badge ${isBangla ? 'badge-lang-bn' : 'badge-lang-en'}`}>
            {isBangla ? '🇧🇩 Bangla' : '🇺🇸 English'}
          </span>
          {book?.voice && (
            <span className="badge" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
              <Volume2 size={12} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
              {book.voice}
            </span>
          )}
        </div>
      </div>

      {/* Error Message Box */}
      <ErrorMessageBox error={errorMessage} onDismiss={() => setErrorMessage(null)} />

      {/* Book Title & Header Card */}
      <div
        className="glass-panel"
        style={{
          padding: '24px 28px',
          borderRadius: 'var(--radius-lg)',
          marginBottom: '28px',
          border: '1px solid var(--card-border)',
        }}
      >
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '1.8rem',
            fontWeight: 800,
            color: 'var(--text-primary)',
            marginBottom: '8px',
          }}
        >
          {book?.title}
        </h1>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <span style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
            Original file: <code>{book?.original_filename}</code>
          </span>

          <span
            className="badge"
            style={{
              background: book?.status === 'ready' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(99, 102, 241, 0.15)',
              color: book?.status === 'ready' ? '#34d399' : '#818cf8',
              fontSize: '0.82rem',
              padding: '4px 10px',
            }}
          >
            {isGenerating ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                Generating audio ({doneChunks}/{totalChunks} done)
              </span>
            ) : (
              `Narration ${book?.status}`
            )}
          </span>
        </div>

        {/* Progress Track */}
        <div className="progress-track" style={{ height: '6px', margin: '14px 0 6px' }}>
          <div
            className="progress-fill"
            style={{ width: `${book?.status === 'ready' ? 100 : progressPercent}%` }}
          />
        </div>
      </div>

      {/* Ordered Chunks Narrative List */}
      <div className="chunks-list" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {chunks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            No narrative sentences found yet.
          </div>
        ) : (
          chunks.map((chunk) => {
            const isActive = chunk.index === activeChunkIndex;
            const isDone = chunk.status === 'done';
            const isChunkFailed = chunk.status === 'failed';
            const isChunkGenerating = chunk.status === 'pending' || !isDone;

            return (
              <div
                key={chunk.id || chunk.index}
                ref={isActive ? activeChunkCardRef : null}
                className={`chunk-row ${isActive ? 'active' : ''}`}
                onClick={() => playChunk(chunk.index, 0)}
                style={{
                  background: isActive ? 'var(--chunk-active-bg)' : 'var(--card-bg)',
                  border: isActive
                    ? '1.5px solid var(--accent-primary)'
                    : '1px solid var(--card-border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '18px 22px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  boxShadow: isActive ? 'var(--chunk-active-shadow)' : 'none',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '16px',
                }}
              >
                {/* Play / Status Indicator Icon */}
                <button
                  type="button"
                  className="chunk-play-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (isActive && isPlaying) {
                      pause();
                    } else {
                      playChunk(chunk.index, 0);
                    }
                  }}
                  title={isActive && isPlaying ? 'Pause' : 'Play sentence'}
                  aria-label={isActive && isPlaying ? 'Pause' : 'Play sentence'}
                >
                  {isChunkGenerating ? (
                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                  ) : isActive && isPlaying ? (
                    <Pause size={16} />
                  ) : (
                    <Play size={16} style={{ marginLeft: '2px' }} />
                  )}
                </button>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          color: isActive ? 'var(--accent-primary)' : 'var(--text-muted)',
                          background: 'var(--bg-tertiary)',
                          padding: '2px 8px',
                          borderRadius: '6px',
                        }}
                      >
                        #{chunk.index}
                      </span>

                      {chunk.duration_seconds && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <Clock size={12} /> {chunk.duration_seconds}s
                        </span>
                      )}
                    </div>

                    {/* Chunk status badge */}
                    {isChunkGenerating ? (
                      <span className="badge badge-generating" style={{ fontSize: '0.72rem', padding: '2px 8px' }}>
                        Generating...
                      </span>
                    ) : isChunkFailed ? (
                      <span style={{ fontSize: '0.72rem', color: '#ef4444', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <AlertTriangle size={12} /> Failed
                      </span>
                    ) : null}
                  </div>

                  {/* Sentence Narrative Text */}
                  <p
                    className="chunk-text"
                    style={{
                      fontFamily: 'var(--font-story)',
                      fontSize: isBangla ? '1.2rem' : '1.08rem',
                      lineHeight: 1.85,
                      color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                      margin: 0,
                    }}
                  >
                    {chunk.text}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Docked Audio Player */}
      <AudioPlayerBar book={book} chunks={chunks} player={player} />
    </div>
  );
}
