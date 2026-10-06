import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Headphones, Trash2, ArrowRight, Clock, FileText, CheckCircle2, AlertCircle, Loader2, RotateCcw } from 'lucide-react';
import { deleteBook, retryBook } from '../api';

/**
 * List of previously uploaded storybooks with status and progress bars.
 *
 * @param {Object} props
 * @param {Array} props.books - List of books from GET /api/books.
 * @param {function} props.onBookDeleted - Callback(bookId) when a book is deleted.
 * @param {function} [props.onBookUpdated] - Callback(bookId) when a book narration is retried.
 * @param {boolean} props.loading - Loading state flag.
 * @param {function} props.onError - Error reporter callback.
 */
export default function BookList({ books, onBookDeleted, onBookUpdated, loading, onError }) {
  const navigate = useNavigate();
  const [retryingId, setRetryingId] = useState(null);

  const handleRetry = async (e, bookId) => {
    e.stopPropagation();
    try {
      setRetryingId(bookId);
      await retryBook(bookId);
      if (onBookUpdated) onBookUpdated(bookId);
    } catch (err) {
      if (onError) onError(err.message || 'Failed to retry failed chunks');
    } finally {
      setRetryingId(null);
    }
  };

  const handleDelete = async (e, bookId, bookTitle) => {
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to delete "${bookTitle}"?`)) {
      try {
        await deleteBook(bookId);
        if (onBookDeleted) onBookDeleted(bookId);
      } catch (err) {
        if (onError) onError(err.message || 'Failed to delete book');
      }
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)' }}>
        <Loader2 size={28} style={{ animation: 'spin 1.2s linear infinite', margin: '0 auto 12px', display: 'block', color: 'var(--accent-primary)' }} />
        Loading your storybooks...
      </div>
    );
  }

  if (!books || books.length === 0) {
    return (
      <div className="glass-panel" style={{ textAlign: 'center', padding: '48px 24px', margin: '20px auto', maxWidth: '720px' }}>
        <div
          style={{
            width: '60px',
            height: '60px',
            borderRadius: '50%',
            background: 'var(--bg-tertiary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            color: 'var(--text-muted)',
          }}
        >
          <BookOpen size={30} />
        </div>
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.25rem', marginBottom: '8px', color: 'var(--text-primary)' }}>
          No storybooks in your library yet
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', maxWidth: '440px', margin: '0 auto' }}>
          Upload any English or Bangla storybook PDF above to begin immersive voice narration and read-along!
        </p>
      </div>
    );
  }

  return (
    <section className="library-section" style={{ maxWidth: '1080px', margin: '36px auto 60px' }}>
      <div className="section-header" style={{ marginBottom: '22px' }}>
        <h2 className="section-title">
          <BookOpen size={24} style={{ color: 'var(--accent-primary)' }} />
          Your Storybook Library ({books.length})
        </h2>
      </div>

      <div className="book-grid">
        {books.map((book) => {
          const totalChunks = book.total_chunks || 0;
          const doneChunks = book.done_chunks || 0;
          const progressPercent = totalChunks > 0 ? Math.round((doneChunks / totalChunks) * 100) : 0;
          const isBangla = book.language === 'bn';
          const isReady = book.status === 'ready';
          const isFailed = book.status === 'failed';
          const isGenerating = book.status === 'generating' || book.status === 'extracting';

          return (
            <div
              key={book.id}
              className="book-card"
              onClick={() => navigate(`/book/${book.id}`)}
              style={{ cursor: 'pointer' }}
            >
              <div>
                <div className="book-card-header">
                  <div className="book-card-icon">
                    <BookOpen size={24} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h3 className="book-card-title" title={book.title}>
                      {book.title}
                    </h3>
                    <div className="book-badges">
                      <span className={`badge ${isBangla ? 'badge-lang-bn' : 'badge-lang-en'}`}>
                        {isBangla ? '🇧🇩 Bangla' : '🇺🇸 English'}
                      </span>

                      {book.provider && (
                        <span
                          className="badge"
                          style={{
                            background: book.provider === 'elevenlabs' ? 'rgba(236, 72, 153, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                            color: book.provider === 'elevenlabs' ? '#f472b6' : '#60a5fa',
                            border: `1px solid ${
                              book.provider === 'elevenlabs' ? 'rgba(236, 72, 153, 0.3)' : 'rgba(59, 130, 246, 0.3)'
                            }`,
                            fontSize: '0.74rem',
                          }}
                        >
                          {book.provider === 'elevenlabs' ? 'ElevenLabs' : 'Edge TTS'}
                        </span>
                      )}

                      {book.multi_voice && (
                        <span
                          className="badge"
                          style={{
                            background: 'rgba(16, 185, 129, 0.15)',
                            color: '#34d399',
                            border: '1px solid rgba(16, 185, 129, 0.3)',
                            fontSize: '0.74rem',
                          }}
                        >
                          🎭 Cast Mode
                        </span>
                      )}

                      {book.is_scanned && (
                        <span
                          className="badge"
                          style={{
                            background: 'rgba(245, 158, 11, 0.15)',
                            color: '#fbbf24',
                            border: '1px solid rgba(245, 158, 11, 0.35)',
                          }}
                        >
                          Scanned / OCR
                        </span>
                      )}

                      {book.total_characters > 0 && (
                        <span
                          className="badge"
                          style={{
                            background: book.total_characters >= 10000 ? 'rgba(245, 158, 11, 0.15)' : 'var(--bg-tertiary)',
                            color: book.total_characters >= 10000 ? '#fbbf24' : 'var(--text-secondary)',
                            border: book.total_characters >= 10000 ? '1px solid rgba(245, 158, 11, 0.35)' : 'none',
                          }}
                          title={`${book.total_characters.toLocaleString()} characters`}
                        >
                          {book.total_characters >= 10000 && <AlertCircle size={11} style={{ marginRight: '4px', verticalAlign: 'middle', display: 'inline' }} />}
                          {book.total_characters >= 1000
                            ? `${(book.total_characters / 1000).toFixed(1)}k chars`
                            : `${book.total_characters} chars`}
                        </span>
                      )}

                      {/* Status Badge */}
                      <span
                        className="badge"
                        style={{
                          background: isReady
                            ? 'rgba(16, 185, 129, 0.15)'
                            : isFailed
                            ? 'rgba(239, 68, 68, 0.15)'
                            : 'rgba(99, 102, 241, 0.15)',
                          color: isReady ? '#34d399' : isFailed ? '#f87171' : '#818cf8',
                          border: `1px solid ${
                            isReady
                              ? 'rgba(16, 185, 129, 0.3)'
                              : isFailed
                              ? 'rgba(239, 68, 68, 0.3)'
                              : 'rgba(99, 102, 241, 0.3)'
                          }`,
                          textTransform: 'capitalize',
                        }}
                      >
                        {book.status}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="progress-track">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${Math.min(100, Math.max(isReady ? 100 : 0, progressPercent))}%`,
                      background: isFailed
                        ? '#ef4444'
                        : 'linear-gradient(90deg, var(--accent-primary), #10b981)',
                    }}
                  />
                </div>

                <div className="progress-text">
                  <span>Narration Progress</span>
                  <span>
                    {doneChunks}/{totalChunks} chunks ({isReady ? '100%' : `${progressPercent}%`})
                  </span>
                </div>

                {book.cost_warning && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 10px',
                      marginTop: '10px',
                      borderRadius: 'var(--radius-sm)',
                      background: 'rgba(245, 158, 11, 0.1)',
                      border: '1px solid rgba(245, 158, 11, 0.3)',
                      color: '#fbbf24',
                      fontSize: '0.78rem',
                      lineHeight: 1.3,
                    }}
                    title={book.cost_warning}
                  >
                    <AlertCircle size={13} style={{ flexShrink: 0, color: '#f59e0b' }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {book.cost_warning}
                    </span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="book-card-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ flex: 1, padding: '8px 14px', fontSize: '0.85rem' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/book/${book.id}`);
                  }}
                >
                  <Headphones size={16} />
                  Listen & Read
                  <ArrowRight size={14} />
                </button>

                {(isFailed || (totalChunks > 0 && doneChunks < totalChunks && !isGenerating)) && (
                  <button
                    type="button"
                    className="btn btn-secondary book-retry-btn"
                    style={{
                      padding: '8px 12px',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      color: '#f87171',
                      borderColor: 'rgba(239, 68, 68, 0.4)',
                      background: 'rgba(239, 68, 68, 0.1)',
                    }}
                    disabled={retryingId === book.id}
                    onClick={(e) => handleRetry(e, book.id)}
                    title="Retry failed chunks"
                  >
                    {retryingId === book.id ? (
                      <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                    ) : (
                      <RotateCcw size={14} />
                    )}
                    Retry
                  </button>
                )}

                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: '8px 10px', color: '#ef4444' }}
                  onClick={(e) => handleDelete(e, book.id, book.title)}
                  title="Delete Book"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
