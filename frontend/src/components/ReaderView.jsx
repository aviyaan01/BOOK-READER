import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Pause,
  Loader2,
  Sparkles,
  Headphones,
  ArrowLeft,
  Volume2,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { generateChunkAudio, generateAllBookAudio } from '../api';

export default function ReaderView({
  book,
  voices,
  selectedVoice,
  onVoiceChange,
  activeChunkIndex,
  isPlaying,
  onPlayChunk,
  onPause,
  onBack,
  onBookUpdated,
}) {
  const [isGeneratingAll, setIsGeneratingAll] = useState(false);
  const [batchProgress, setBatchProgress] = useState(null);
  const [generatingChunkId, setGeneratingChunkId] = useState(null);
  const activeChunkRef = useRef(null);

  // Auto-scroll active chunk into view smoothly
  useEffect(() => {
    if (activeChunkRef.current) {
      activeChunkRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [activeChunkIndex]);

  const handlePlayOrGenerateChunk = async (chunk) => {
    if (activeChunkIndex === chunk.chunk_index && isPlaying) {
      onPause();
      return;
    }

    // If audio is already ready, play it directly
    if (chunk.audio_status === 'ready' && chunk.audio_path) {
      onPlayChunk(chunk.chunk_index);
      return;
    }

    // Otherwise generate audio for this chunk on the fly
    try {
      setGeneratingChunkId(chunk.id);
      const updatedChunk = await generateChunkAudio(book.id, chunk.id, {
        voice: selectedVoice,
      });

      // Update book state
      if (onBookUpdated) {
        const newChunks = book.chunks.map((c) =>
          c.id === updatedChunk.id ? updatedChunk : c
        );
        onBookUpdated({ ...book, chunks: newChunks });
      }

      // Automatically play once synthesized
      onPlayChunk(chunk.chunk_index);
    } catch (err) {
      alert(`Synthesis failed: ${err.message}`);
    } finally {
      setGeneratingChunkId(null);
    }
  };

  const handleGenerateAll = async () => {
    if (isGeneratingAll) return;
    try {
      setIsGeneratingAll(true);
      setBatchProgress('Synthesizing storytelling voices...');
      const res = await generateAllBookAudio(book.id, {
        voice: selectedVoice,
        overwrite: false,
      });
      setBatchProgress(`Done! ${res.successful} chunks generated.`);
      // Reload book details
      if (onBookUpdated) {
        onBookUpdated(null); // Triggers re-fetch
      }
    } catch (err) {
      alert(`Batch generation failed: ${err.message}`);
    } finally {
      setIsGeneratingAll(false);
      setTimeout(() => setBatchProgress(null), 3000);
    }
  };

  // Group chunks by page number
  const chunksByPage = (book.chunks || []).reduce((acc, chunk) => {
    const page = chunk.page_number || 1;
    if (!acc[page]) acc[page] = [];
    acc[page].push(chunk);
    return acc;
  }, {});

  const totalChunks = book.chunks ? book.chunks.length : 0;
  const readyChunks = book.chunks ? book.chunks.filter((c) => c.audio_status === 'ready').length : 0;
  const isBangla = book.language === 'bn';

  return (
    <div className="reader-view-container" data-lang={book.language}>
      {/* Top sticky controls bar */}
      <div className="reader-header">
        <div className="reader-header-left">
          <button className="btn btn-secondary" onClick={onBack} title="Back to Library">
            <ArrowLeft size={16} />
            Back
          </button>
          <div>
            <h1 className="reader-book-title">{book.title}</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <span className={`badge ${isBangla ? 'badge-lang-bn' : 'badge-lang-en'}`}>
                {isBangla ? '🇧🇩 Bangla Narration' : '🇺🇸 English Narration'}
              </span>
              <span className="badge">
                {readyChunks}/{totalChunks} audio ready
              </span>
            </div>
          </div>
        </div>

        <div className="reader-controls">
          {/* Storyteller Voice Picker */}
          <div className="voice-select-wrap">
            <Volume2 size={16} style={{ color: 'var(--accent-primary)' }} />
            <select
              value={selectedVoice}
              onChange={(e) => onVoiceChange(e.target.value)}
              title="Select Storyteller Voice"
            >
              {voices
                .filter((v) => !book.language || v.language === book.language)
                .map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.name} ({voice.gender})
                  </option>
                ))}
            </select>
          </div>

          {/* Batch Synthesize All Audio */}
          <button
            className="btn btn-primary"
            onClick={handleGenerateAll}
            disabled={isGeneratingAll || readyChunks === totalChunks}
            style={{ fontSize: '0.85rem' }}
          >
            {isGeneratingAll ? (
              <>
                <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                Narrating Book...
              </>
            ) : (
              <>
                <Sparkles size={16} />
                {readyChunks === totalChunks ? 'All Audio Ready' : 'Narrate Entire Book'}
              </>
            )}
          </button>
        </div>
      </div>

      {batchProgress && (
        <div
          style={{
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--accent-glow)',
            color: 'var(--accent-primary)',
            padding: '10px 18px',
            borderRadius: '12px',
            marginBottom: '20px',
            textAlign: 'center',
            fontSize: '0.88rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
          }}
        >
          <RefreshCw size={16} className="spin-animation" />
          {batchProgress}
        </div>
      )}

      {/* Story Narrative Text Chunks */}
      <main className="story-scroll-area">
        {Object.entries(chunksByPage).map(([pageStr, pageChunks]) => (
          <div key={`page-${pageStr}`} className="page-section">
            <div className="page-divider">
              <span>Page {pageStr}</span>
            </div>

            {pageChunks.map((chunk) => {
              const isThisActive = activeChunkIndex === chunk.chunk_index;
              const isThisPlaying = isThisActive && isPlaying;
              const isGeneratingThis = generatingChunkId === chunk.id;
              const isReady = chunk.audio_status === 'ready';

              return (
                <article
                  key={chunk.id}
                  ref={isThisActive ? activeChunkRef : null}
                  className={`chunk-row ${isThisActive ? 'active' : ''}`}
                  onClick={() => handlePlayOrGenerateChunk(chunk)}
                  title={isReady ? 'Click to play' : 'Click to generate audio and play'}
                >
                  {/* Play / Generating Button */}
                  <button
                    className="chunk-play-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePlayOrGenerateChunk(chunk);
                    }}
                    disabled={isGeneratingThis}
                    aria-label={isThisPlaying ? "Pause narration" : "Play narration"}
                  >
                    {isGeneratingThis ? (
                      <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                    ) : isThisPlaying ? (
                      <Pause size={16} />
                    ) : (
                      <Play size={16} style={{ marginLeft: '2px' }} />
                    )}
                  </button>

                  <div className="chunk-content">
                    <div className="chunk-meta">
                      <span>Sentence {chunk.chunk_index}</span>
                      {isReady && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#10b981' }}>
                          <CheckCircle2 size={12} />
                          Audio Ready {chunk.duration_seconds ? `(${chunk.duration_seconds.toFixed(1)}s)` : ''}
                        </span>
                      )}
                      {chunk.audio_status === 'pending' && (
                        <span style={{ color: 'var(--text-muted)' }}>Click to Narrate</span>
                      )}
                      {isThisPlaying && (
                        <div className="audio-wave-bars">
                          <span className="audio-bar" />
                          <span className="audio-bar" />
                          <span className="audio-bar" />
                          <span className="audio-bar" />
                        </div>
                      )}
                    </div>

                    <p className="chunk-text">{chunk.text}</p>
                  </div>
                </article>
              );
            })}
          </div>
        ))}
      </main>
    </div>
  );
}
