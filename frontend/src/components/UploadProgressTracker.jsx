import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Headphones, Loader2, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';
import { fetchBook } from '../api';

/**
 * Polls GET /api/books/{id} every 2 seconds, showing progress and the "Start listening" button.
 *
 * @param {Object} props
 * @param {string} props.bookId - ID of the newly uploaded book.
 * @param {function} [props.onStatusChange] - Optional callback when status or progress changes.
 * @param {function} [props.onError] - Callback to report failure message.
 */
export default function UploadProgressTracker({ bookId, onStatusChange, onError }) {
  const navigate = useNavigate();
  const [book, setBook] = useState(null);
  const [pollingError, setPollingError] = useState(null);

  useEffect(() => {
    if (!bookId) return;

    let isMounted = true;

    async function poll() {
      try {
        const data = await fetchBook(bookId);
        if (!isMounted) return;

        setBook(data);
        if (onStatusChange) onStatusChange(data);

        // Stop polling if complete or failed
        if (data.status === 'ready') {
          return true; // Stop
        }
        if (data.status === 'failed') {
          if (onError && data.error_message) {
            onError(`Audiobook narration failed: ${data.error_message}`);
          }
          return true; // Stop
        }
      } catch (err) {
        if (!isMounted) return;
        setPollingError(err.message);
      }
      return false;
    }

    // Initial check immediately
    poll();

    // Poll every 2 seconds as required
    const intervalId = setInterval(async () => {
      const shouldStop = await poll();
      if (shouldStop) {
        clearInterval(intervalId);
      }
    }, 2000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [bookId]);

  if (!bookId || !book) {
    return (
      <div
        className="glass-panel"
        style={{
          padding: '20px 24px',
          maxWidth: '720px',
          margin: '0 auto 32px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: 'var(--text-secondary)',
          borderRadius: 'var(--radius-lg)',
        }}
      >
        <Loader2 size={20} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent-primary)' }} />
        <span>Initializing background narration pipeline...</span>
      </div>
    );
  }

  const { status, total_chunks = 0, done_chunks = 0, progress_percent = 0, title } = book;

  // Format progress text as required: "Generating audio: 34%"
  let progressStatusText = '';
  if (status === 'uploaded') {
    progressStatusText = 'Storybook uploaded, preparing extractor...';
  } else if (status === 'extracting') {
    progressStatusText = 'Extracting story text and splitting sentences...';
  } else if (status === 'generating') {
    progressStatusText = `Generating audio: ${progress_percent}%`;
  } else if (status === 'ready') {
    progressStatusText = 'Audiobook ready to listen!';
  } else if (status === 'failed') {
    progressStatusText = 'Processing encountered an error.';
  } else {
    progressStatusText = `Processing: ${status}`;
  }

  // "When at least 2 chunks are done, show a 'Start listening' button."
  // Also show if all chunks are done (e.g., short 1-chunk story)
  const canStartListening =
    done_chunks >= 2 || (done_chunks >= 1 && (status === 'ready' || done_chunks === total_chunks));

  const isFailed = status === 'failed';
  const isReady = status === 'ready';

  return (
    <div
      className="glass-panel"
      style={{
        padding: '24px 28px',
        maxWidth: '720px',
        margin: '0 auto 36px',
        borderRadius: 'var(--radius-lg)',
        border: isFailed
          ? '1px solid rgba(239, 68, 68, 0.4)'
          : isReady
          ? '1px solid rgba(16, 185, 129, 0.4)'
          : '1px solid var(--accent-primary)',
        boxShadow: 'var(--shadow-md)',
        background: 'var(--card-bg)',
        animation: 'fadeIn 0.3s ease',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isReady ? (
            <CheckCircle2 size={22} style={{ color: '#10b981' }} />
          ) : isFailed ? (
            <AlertTriangle size={22} style={{ color: '#ef4444' }} />
          ) : (
            <Loader2 size={22} style={{ color: 'var(--accent-primary)', animation: 'spin 1.2s linear infinite' }} />
          )}
          <div>
            <h4 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              {title || 'Current Book'}
            </h4>
            <div style={{ fontSize: '0.85rem', color: isFailed ? '#ef4444' : isReady ? '#10b981' : 'var(--text-accent)', fontWeight: 600 }}>
              {progressStatusText}
            </div>
          </div>
        </div>

        {/* Progress ratio tag */}
        <span
          className="badge"
          style={{
            fontSize: '0.8rem',
            padding: '4px 10px',
            background: 'var(--bg-tertiary)',
            color: 'var(--text-secondary)',
          }}
        >
          {total_chunks > 0 ? `${done_chunks}/${total_chunks} chunks` : 'Processing'}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="progress-track" style={{ height: '8px', margin: '10px 0 16px', background: 'var(--bg-tertiary)' }}>
        <div
          className="progress-fill"
          style={{
            width: `${Math.min(100, Math.max(isReady ? 100 : 0, progress_percent))}%`,
            background: isFailed
              ? '#ef4444'
              : 'linear-gradient(90deg, var(--accent-primary), #10b981)',
          }}
        />
      </div>

      {/* Action Area: Start Listening Button */}
      {canStartListening && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '14px' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate(`/book/${bookId}`)}
            style={{
              padding: '10px 20px',
              fontSize: '0.92rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              borderColor: '#10b981',
              boxShadow: '0 4px 14px rgba(16, 185, 129, 0.3)',
            }}
          >
            <Headphones size={18} />
            Start listening
            <ArrowRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
