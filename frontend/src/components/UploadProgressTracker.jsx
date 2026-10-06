import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Headphones, Loader2, CheckCircle2, AlertTriangle, ArrowRight, RotateCcw } from 'lucide-react';
import { fetchBook, retryBook } from '../api';

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
  const [retrying, setRetrying] = useState(false);
  const [pollKey, setPollKey] = useState(0);

  const handleRetry = async () => {
    try {
      setRetrying(true);
      await retryBook(bookId);
      setBook((prev) => (prev ? { ...prev, status: 'generating', error_message: null } : prev));
      setPollKey((k) => k + 1);
    } catch (err) {
      if (onError) onError(err.message || 'Failed to retry failed chunks');
    } finally {
      setRetrying(false);
    }
  };

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
  }, [bookId, pollKey]);

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

  const {
    status,
    total_chunks = 0,
    done_chunks = 0,
    progress_percent = 0,
    title,
    is_scanned,
    warning_message,
    total_characters = 0,
    cost_warning,
  } = book;

  // Format progress text as required: "Generating audio: 34%"
  let progressStatusText = '';
  if (status === 'uploaded') {
    progressStatusText = 'Storybook uploaded, preparing extractor...';
  } else if (status === 'extracting') {
    progressStatusText = is_scanned
      ? 'Recognizing text via OCR (scanned PDF)...'
      : 'Extracting story text and splitting sentences...';
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
  const hasFailedChunks = isFailed || (total_chunks > 0 && done_chunks < total_chunks && status !== 'generating' && status !== 'extracting' && status !== 'ready');

  return (
    <div
      className="glass-panel"
      style={{
        padding: '24px 28px',
        maxWidth: '720px',
        margin: '0 auto 36px',
        borderRadius: 'var(--radius-lg)',
        border: isFailed || hasFailedChunks
          ? '1px solid rgba(239, 68, 68, 0.4)'
          : isReady
          ? '1px solid rgba(16, 185, 129, 0.4)'
          : '1px solid var(--accent-primary)',
        boxShadow: 'var(--shadow-md)',
        background: 'var(--card-bg)',
        animation: 'fadeIn 0.3s ease',
      }}
    >
      {/* Scanned PDF warning message */}
      {(is_scanned || warning_message) && (
        <div
          className="scanned-pdf-warning"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '12px 16px',
            marginBottom: '16px',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            color: '#fbbf24',
            fontSize: '0.88rem',
            lineHeight: 1.4,
          }}
        >
          <AlertTriangle size={18} style={{ flexShrink: 0, color: '#f59e0b' }} />
          <span>
            {warning_message || 'This looks like a scanned PDF, text recognition may take longer and can contain errors.'}
          </span>
        </div>
      )}

      {/* Cost & Size Warning Banner */}
      {(cost_warning || total_characters >= 10000) && (
        <div
          className="cost-size-warning"
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            padding: '12px 16px',
            marginBottom: '16px',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            color: '#fbbf24',
            fontSize: '0.88rem',
            lineHeight: 1.4,
          }}
        >
          <AlertTriangle size={18} style={{ flexShrink: 0, color: '#f59e0b', marginTop: '2px' }} />
          <div>
            <strong>Cost &amp; Size Warning:</strong>{' '}
            {cost_warning ||
              `Large storybook detected (${total_characters.toLocaleString()} characters, ~${Math.max(1, Math.round(total_characters / 900))} min audio). Narration synthesis and AI cleanup take more processing time and API quota.`}
          </div>
        </div>
      )}

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

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {total_characters > 0 && (
            <span
              className="badge"
              style={{
                fontSize: '0.8rem',
                padding: '4px 10px',
                background: total_characters >= 10000 ? 'rgba(245, 158, 11, 0.15)' : 'var(--bg-tertiary)',
                color: total_characters >= 10000 ? '#fbbf24' : 'var(--text-secondary)',
                border: total_characters >= 10000 ? '1px solid rgba(245, 158, 11, 0.35)' : 'none',
              }}
              title={`${total_characters.toLocaleString()} total characters`}
            >
              {total_characters.toLocaleString()} chars
            </span>
          )}

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

      {/* Action Area: Start Listening & Retry Failed Chunks */}
      {(canStartListening || hasFailedChunks) && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '12px', marginTop: '14px' }}>
          {hasFailedChunks && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleRetry}
              disabled={retrying}
              style={{
                padding: '9px 18px',
                fontSize: '0.9rem',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                background: 'rgba(239, 68, 68, 0.12)',
                borderColor: 'rgba(239, 68, 68, 0.4)',
                color: '#f87171',
              }}
            >
              {retrying ? (
                <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <RotateCcw size={16} />
              )}
              Retry Failed Chunks
            </button>
          )}

          {canStartListening && (
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
          )}
        </div>
      )}
    </div>
  );
}
