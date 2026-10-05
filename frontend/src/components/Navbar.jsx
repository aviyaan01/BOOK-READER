import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { BookOpen, Moon, Sun } from 'lucide-react';

export default function Navbar({ theme, onThemeChange }) {
  const navigate = useNavigate();
  const location = useLocation();
  const isPlayerPage = location.pathname.startsWith('/book/');

  return (
    <header className="navbar">
      <div
        className="nav-brand"
        onClick={() => navigate('/')}
        title="Go to Storybook Library"
        style={{ cursor: 'pointer' }}
      >
        <div className="brand-icon-wrapper">
          <BookOpen size={22} />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="brand-title">PDF Storyteller</span>
            <span className="brand-tag">Neural</span>
          </div>
          <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
            Expressive Bangla & English Audiobooks
          </div>
        </div>
      </div>

      <div className="nav-actions">
        {isPlayerPage && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/')}
            style={{ padding: '6px 14px', fontSize: '0.84rem' }}
          >
            ← Library
          </button>
        )}

        {/* Theme Switcher */}
        <div className="theme-selector">
          <button
            type="button"
            className={`theme-btn ${theme === 'dark' ? 'active' : ''}`}
            onClick={() => onThemeChange('dark')}
            title="Midnight Dark"
          >
            <Moon size={14} />
            <span>Dark</span>
          </button>
          <button
            type="button"
            className={`theme-btn ${theme === 'sepia' ? 'active' : ''}`}
            onClick={() => onThemeChange('sepia')}
            title="Warm Sepia"
          >
            <span style={{ fontSize: '13px' }}>📜</span>
            <span>Sepia</span>
          </button>
          <button
            type="button"
            className={`theme-btn ${theme === 'light' ? 'active' : ''}`}
            onClick={() => onThemeChange('light')}
            title="Clean Light"
          >
            <Sun size={14} />
            <span>Light</span>
          </button>
        </div>
      </div>
    </header>
  );
}
