import React from 'react';
import { AlertCircle, X } from 'lucide-react';

/**
 * Reusable visible error message box component.
 *
 * @param {Object} props
 * @param {string|null} props.error - The error message text to display.
 * @param {function} [props.onDismiss] - Optional callback when the user clicks the dismiss button.
 */
export default function ErrorMessageBox({ error, onDismiss }) {
  if (!error) return null;

  return (
    <div
      role="alert"
      className="error-message-box"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        padding: '14px 18px',
        borderRadius: '12px',
        background: 'rgba(239, 68, 68, 0.12)',
        border: '1px solid rgba(239, 68, 68, 0.35)',
        color: '#f87171',
        fontSize: '0.9rem',
        lineHeight: 1.5,
        margin: '16px 0 24px',
        boxShadow: '0 4px 16px rgba(239, 68, 68, 0.15)',
        backdropFilter: 'blur(8px)',
        position: 'relative',
        animation: 'fadeIn 0.25s ease-in-out',
      }}
    >
      <AlertCircle size={20} style={{ flexShrink: 0, marginTop: '2px', color: '#ef4444' }} />
      <div style={{ flex: 1, wordBreak: 'break-word' }}>
        <strong style={{ display: 'block', marginBottom: '2px', color: '#fca5a5' }}>
          Notice
        </strong>
        {error}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss error"
          style={{
            background: 'none',
            border: 'none',
            color: '#fca5a5',
            cursor: 'pointer',
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '6px',
            transition: 'background 0.2s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
}
