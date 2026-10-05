import React, { useState, useEffect, useRef } from 'react';
import { UploadCloud, FileText, Loader2, Sparkles, CheckCircle, Volume2, Globe } from 'lucide-react';
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
  const [language, setLanguage] = useState('bn'); // 'bn' | 'en'
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('');
  const [loadingVoices, setLoadingVoices] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);

  // Fetch available voices whenever language changes
  useEffect(() => {
    let isCancelled = false;
    async function loadVoicesForLanguage() {
      try {
        setLoadingVoices(true);
        const data = await fetchVoices(language);
        if (isCancelled) return;
        setVoices(data || []);

        // Pick recommended voice for selected language
        if (data && data.length > 0) {
          const defaultVoice = language === 'bn'
            ? data.find((v) => v.ShortName === 'bn-BD-NabanitaNeural' || v.name === 'bn-BD-NabanitaNeural') || data[0]
            : data.find((v) => v.ShortName === 'en-US-AriaNeural' || v.name === 'en-US-AriaNeural') || data[0];
          setSelectedVoice(defaultVoice.ShortName || defaultVoice.name || '');
        } else {
          setSelectedVoice('');
        }
      } catch (err) {
        if (!isCancelled) {
          console.warn('Could not load voices:', err);
          // Fallback voices
          if (language === 'bn') {
            setSelectedVoice('bn-BD-NabanitaNeural');
          } else {
            setSelectedVoice('en-US-AriaNeural');
          }
        }
      } finally {
        if (!isCancelled) setLoadingVoices(false);
      }
    }

    loadVoicesForLanguage();
    return () => {
      isCancelled = true;
    };
  }, [language]);

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

      const result = await uploadBookPdf(selectedFile, language, selectedVoice);

      // Reset file input
      setSelectedFile(null);
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

        {/* Form Controls: Language & Voice */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '16px',
            marginTop: '22px',
          }}
        >
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
