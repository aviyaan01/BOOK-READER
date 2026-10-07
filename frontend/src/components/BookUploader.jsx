import React, { useState, useEffect, useRef } from 'react';
import { UploadCloud, FileText, Loader2, Sparkles, Volume2, Globe, Cpu, Users } from 'lucide-react';
import { uploadBookPdf, fetchVoices } from '../api';

const MAX_FILE_SIZE_BYTES = 30 * 1024 * 1024; // 30 MB

/**
 * Storybook PDF Uploader with Drag-and-Drop, Language, and Voice selection.
 *
 * @param {Object} props
 * @param {function} props.onUploadSuccess - Callback({ id, status }) after upload succeeds.
 * @param {function} props.onError - Callback(errorMessage) to show in visible message box.
 */
export default function BookUploader({ onUploadSuccess, onError }) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [provider, setProvider] = useState('edge_tts'); // 'edge_tts' | 'elevenlabs'
  const [language, setLanguage] = useState('bn'); // 'bn' | 'en'
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('');
  const [loadingVoices, setLoadingVoices] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [improveWithAi, setImproveWithAi] = useState(false);
  const [multiVoice, setMultiVoice] = useState(false);
  const fileInputRef = useRef(null);

  // Fetch available voices whenever language or provider changes
  useEffect(() => {
    let isCancelled = false;
    async function loadVoicesForProviderAndLanguage() {
      try {
        setLoadingVoices(true);
        const data = await fetchVoices(language, provider);
        if (isCancelled) return;
        setVoices(data || []);

        // Pick recommended voice for selected provider and language
        if (data && data.length > 0) {
          let defaultVoice;
          if (provider === 'elevenlabs') {
            defaultVoice =
              data.find((v) => v.name === 'Rachel' || v.ShortName === '21m00Tcm4TlvDq8ikWAM') ||
              data[0];
          } else {
            defaultVoice = language === 'bn'
              ? data.find((v) => v.ShortName === 'bn-BD-NabanitaNeural' || v.name === 'bn-BD-NabanitaNeural') || data[0]
              : data.find((v) => v.ShortName === 'en-US-AriaNeural' || v.name === 'en-US-AriaNeural') || data[0];
          }
          setSelectedVoice(defaultVoice.ShortName || defaultVoice.name || defaultVoice.voice_id || '');
        } else {
          setSelectedVoice('');
        }
      } catch (err) {
        if (!isCancelled) {
          console.warn('Could not load voices:', err);
          if (provider === 'elevenlabs') {
            setSelectedVoice('21m00Tcm4TlvDq8ikWAM');
          } else if (language === 'bn') {
            setSelectedVoice('bn-BD-NabanitaNeural');
          } else {
            setSelectedVoice('en-US-AriaNeural');
          }
        }
      } finally {
        if (!isCancelled) setLoadingVoices(false);
      }
    }

    loadVoicesForProviderAndLanguage();
    return () => {
      isCancelled = true;
    };
  }, [language, provider]);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer?.files;
    if (files && files[0]) {
      validateAndSetFile(files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      if (onError) onError('Invalid file type: Please select a PDF storybook (.pdf).');
      setSelectedFile(null);
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      if (onError) onError(`File exceeds maximum size of 30MB (Selected file: ${(file.size / (1024 * 1024)).toFixed(1)}MB).`);
      setSelectedFile(null);
      return;
    }
    if (onError) onError(null); // Clear previous errors
    setSelectedFile(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      if (onError) onError('Please select a PDF storybook to upload.');
      return;
    }

    try {
      setIsUploading(true);
      if (onError) onError(null);

      const result = await uploadBookPdf(selectedFile, language, selectedVoice, improveWithAi, provider, multiVoice);

      // Reset file input, AI toggle, and multi-voice
      setSelectedFile(null);
      setImproveWithAi(false);
      setMultiVoice(false);
      if (fileInputRef.current) fileInputRef.current.value = '';

      if (onUploadSuccess) {
        onUploadSuccess(result);
      }
    } catch (err) {
      if (onError) {
        onError(err.message || 'Failed to upload PDF storybook.');
      }
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div
      className="glass-panel"
      style={{
        padding: '32px 24px',
        margin: '0 auto 36px',
        maxWidth: '720px',
        border: '1px solid var(--card-border)',
        borderRadius: 'var(--radius-xl)',
      }}
    >
      <form onSubmit={handleSubmit}>
        {/* Drag and Drop Box */}
        <div
          className={`uploader-box ${isDragging ? 'drag-active' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            cursor: 'pointer',
            padding: '36px 20px',
            border: isDragging ? '2px dashed var(--accent-primary)' : '2px dashed var(--card-border)',
            borderRadius: 'var(--radius-lg)',
            background: isDragging ? 'var(--bg-secondary)' : 'var(--bg-tertiary)',
            transition: 'all 0.25s ease',
          }}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".pdf,application/pdf"
            style={{ display: 'none' }}
          />

          <div
            className="uploader-icon-wrap"
            style={{
              width: '60px',
              height: '60px',
              margin: '0 auto 14px',
              borderRadius: '16px',
              background: selectedFile ? 'rgba(16, 185, 129, 0.15)' : 'rgba(99, 102, 241, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: selectedFile ? '#10b981' : 'var(--accent-primary)',
            }}
          >
            {selectedFile ? <FileText size={30} /> : <UploadCloud size={30} />}
          </div>

          <h3
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1.25rem',
              fontWeight: 700,
              marginBottom: '6px',
              color: 'var(--text-primary)',
            }}
          >
            {selectedFile ? selectedFile.name : 'Choose or Drag & Drop PDF Story'}
          </h3>

          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
            {selectedFile ? (
              <span style={{ color: '#10b981', fontWeight: 600 }}>
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready to upload
              </span>
            ) : (
              'Upload storybook in PDF format (Max 30MB)'
            )}
          </p>
        </div>

        {/* Form Controls: Provider, Language & Voice */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
            marginTop: '22px',
          }}
        >
          {/* TTS Engine / Provider Selector */}
          <div>
            <label
              htmlFor="provider-select"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: '6px',
              }}
            >
              <Cpu size={14} style={{ color: 'var(--accent-primary)' }} />
              Voice Engine
            </label>
            <select
              id="provider-select"
              className="select-input"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              style={{ width: '100%', height: '42px' }}
            >
              <option value="edge_tts">Microsoft Edge TTS (Free)</option>
              <option value="elevenlabs">ElevenLabs (AI Storyteller)</option>
            </select>
          </div>

          {/* Language Selector */}
          <div>
            <label
              htmlFor="language-select"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: '6px',
              }}
            >
              <Globe size={14} style={{ color: 'var(--accent-primary)' }} />
              Story Language
            </label>
            <select
              id="language-select"
              className="select-input"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              style={{ width: '100%', height: '42px' }}
            >
              <option value="bn">🇧🇩 Bangla (বাংলা)</option>
              <option value="en">🇺🇸 English</option>
            </select>
          </div>

          {/* Voice Selector */}
          <div>
            <label
              htmlFor="voice-select"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: '6px',
              }}
            >
              <Volume2 size={14} style={{ color: 'var(--accent-primary)' }} />
              Narrator Voice {loadingVoices && '(loading...)'}
            </label>
            <select
              id="voice-select"
              className="select-input"
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              disabled={loadingVoices || voices.length === 0}
              style={{ width: '100%', height: '42px' }}
            >
              {voices.length > 0 ? (
                voices.map((v) => {
                  const voiceKey = v.ShortName || v.name;
                  const friendly =
                    v.FriendlyName ||
                    `${v.LocaleName || v.Locale} - ${voiceKey} (${v.Gender || 'Narrator'})`;
                  return (
                    <option key={voiceKey} value={voiceKey}>
                      {friendly}
                    </option>
                  );
                })
              ) : (
                <option value={selectedVoice || ''}>
                  {selectedVoice || (language === 'bn' ? 'bn-BD-NabanitaNeural' : 'en-US-AriaNeural')}
                </option>
              )}
            </select>
          </div>
        </div>

        {/* Toggle: Improve text with AI (needs API key) */}
        <div
          style={{
            marginTop: '18px',
            padding: '12px 18px',
            background: 'var(--bg-tertiary)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--card-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <label
            htmlFor="improve-with-ai-checkbox"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              cursor: 'pointer',
              userSelect: 'none',
              fontSize: '0.9rem',
              fontWeight: 500,
              color: 'var(--text-primary)',
            }}
          >
            <input
              type="checkbox"
              id="improve-with-ai-checkbox"
              checked={improveWithAi}
              onChange={(e) => setImproveWithAi(e.target.checked)}
              style={{
                width: '18px',
                height: '18px',
                cursor: 'pointer',
                accentColor: 'var(--accent-primary)',
              }}
            />
            <span>Improve text with AI (needs API key)</span>
          </label>

          <span
            className="badge"
            style={{
              fontSize: '0.74rem',
              color: improveWithAi ? 'var(--accent-primary)' : 'var(--text-muted)',
              background: improveWithAi ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
              border: `1px solid ${improveWithAi ? 'rgba(99, 102, 241, 0.3)' : 'transparent'}`,
            }}
          >
            Claude Restoration
          </span>
        </div>

        {/* Toggle: Multi-Voice Narration */}
        <div
          style={{
            marginTop: '10px',
            padding: '12px 18px',
            background: multiVoice ? 'rgba(16, 185, 129, 0.05)' : 'var(--bg-tertiary)',
            borderRadius: 'var(--radius-md)',
            border: `1px solid ${multiVoice ? 'rgba(16, 185, 129, 0.3)' : 'var(--card-border)'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            transition: 'all 0.2s ease',
          }}
        >
          <label
            htmlFor="multi-voice-checkbox"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              cursor: 'pointer',
              userSelect: 'none',
              fontSize: '0.9rem',
              fontWeight: 500,
              color: 'var(--text-primary)',
            }}
          >
            <input
              type="checkbox"
              id="multi-voice-checkbox"
              checked={multiVoice}
              onChange={(e) => setMultiVoice(e.target.checked)}
              style={{
                width: '18px',
                height: '18px',
                cursor: 'pointer',
                accentColor: '#10b981',
              }}
            />
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Users size={14} style={{ color: multiVoice ? '#10b981' : 'var(--text-muted)' }} />
                <span>Multi-Voice Narration</span>
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Claude tags characters — each gets a unique voice
              </div>
            </div>
          </label>

          <span
            className="badge"
            style={{
              fontSize: '0.74rem',
              color: multiVoice ? '#10b981' : 'var(--text-muted)',
              background: multiVoice ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
              border: `1px solid ${multiVoice ? 'rgba(16, 185, 129, 0.3)' : 'transparent'}`,
              whiteSpace: 'nowrap',
            }}
          >
            Cast Mode
          </span>
        </div>

        {/* Upload Button */}
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '24px' }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!selectedFile || isUploading}
            style={{
              minWidth: '240px',
              padding: '12px 28px',
              fontSize: '0.95rem',
              fontWeight: 600,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
            }}
          >
            {isUploading ? (
              <>
                <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
                Uploading Storybook...
              </>
            ) : (
              <>
                <Sparkles size={18} />
                Upload & Narrate
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
