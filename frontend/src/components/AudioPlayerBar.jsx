import React from 'react';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  Gauge,
  Loader2,
  Volume2,
} from 'lucide-react';

/**
 * Docked Audio Player Bar with skip back 10s, speed options, timeline scrubber, and generation state.
 *
 * @param {Object} props
 * @param {Object} props.book - Book metadata
 * @param {Array} props.chunks - List of chunks
 * @param {Object} props.player - Return value from usePlayer hook
 */
export default function AudioPlayerBar({ book, chunks = [], player }) {
  const {
    activeChunkIndex,
    currentChunk,
    isPlaying,
    currentTime,
    duration,
    playbackSpeed,
    speeds,
    isWaitingForGeneration,
    togglePlay,
    prevChunk,
    nextChunk,
    skipBack,
    seekTo,
    changeSpeed,
  } = player;

  const totalChunks = chunks.length;

  const formatTime = (secs) => {
    if (isNaN(secs) || secs < 0) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const hasPrev = chunks.some((c) => c.index < activeChunkIndex && c.status === 'done');
  const hasNext = chunks.some((c) => c.index > activeChunkIndex && c.status === 'done');
  const isChunkReady = currentChunk && currentChunk.status === 'done' && currentChunk.audio_url;

  return (
    <div className="audio-player-dock" role="region" aria-label="Audiobook Player">
      {/* Waiting for generation notification banner */}
      {isWaitingForGeneration && (
        <div className="generating-waiting-card">
          <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
          <span>Generating next sentence narration... Audio will continue automatically once ready.</span>
        </div>
      )}

      <div className="player-inner">
        {/* Left: Book title & sentence indicator */}
        <div className="player-meta">
          <div className="player-meta-title" title={book?.title || 'Storybook'}>
            {book?.title || 'Storybook'}
          </div>
          <div className="player-meta-chunk">
            {currentChunk ? (
              <span>Sentence #{currentChunk.index} of {totalChunks}</span>
            ) : (
              <span>Select a sentence to begin</span>
            )}
            {isWaitingForGeneration && (
              <span className="badge badge-generating" style={{ padding: '1px 6px', fontSize: '0.7rem' }}>
                Generating...
              </span>
            )}
          </div>
        </div>

        {/* Center: Controls & Scrubber */}
        <div className="player-controls-wrap">
          <div className="player-buttons">
            {/* Skip back 10 seconds */}
            <button
              type="button"
              className="player-btn-secondary"
              onClick={() => skipBack(10)}
              title="Skip back 10 seconds"
              disabled={!isChunkReady}
              aria-label="Skip back 10 seconds"
            >
              <RotateCcw size={16} />
              <span style={{ fontSize: '0.62rem', fontWeight: 800, marginLeft: '-14px', marginTop: '10px' }}>
                10
              </span>
            </button>

            {/* Previous Chunk */}
            <button
              type="button"
              className="player-btn-secondary"
              onClick={prevChunk}
              title="Previous Sentence"
              disabled={!hasPrev && currentTime <= 1}
              aria-label="Previous sentence"
            >
              <SkipBack size={18} />
            </button>

            {/* Play / Pause */}
            <button
              type="button"
              className="player-btn-play"
              onClick={togglePlay}
              disabled={!currentChunk}
              title={isPlaying ? 'Pause' : 'Play'}
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isWaitingForGeneration ? (
                <Loader2 size={22} style={{ animation: 'spin 1s linear infinite' }} />
              ) : isPlaying ? (
                <Pause size={22} />
              ) : (
                <Play size={22} style={{ marginLeft: '2px' }} />
              )}
            </button>

            {/* Next Chunk */}
            <button
              type="button"
              className="player-btn-secondary"
              onClick={nextChunk}
              title="Next Sentence"
              disabled={!hasNext && !chunks.some((c) => c.index > activeChunkIndex)}
              aria-label="Next sentence"
            >
              <SkipForward size={18} />
            </button>
          </div>

          {/* Timeline Scrubber Bar */}
          <div className="player-timeline">
            <span className="player-time">{formatTime(currentTime)}</span>
            <input
              type="range"
              className="player-scrubber"
              min="0"
              max={duration > 0 ? duration : 100}
              step="0.1"
              value={currentTime}
              onChange={(e) => seekTo(parseFloat(e.target.value))}
              disabled={!isChunkReady}
              aria-label="Playback timeline"
            />
            <span className="player-time">{formatTime(duration)}</span>
          </div>
        </div>

        {/* Right: Playback Speed selector */}
        <div className="player-extras">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Gauge size={15} style={{ color: 'var(--text-muted)' }} />
            <select
              className="player-select"
              value={playbackSpeed}
              onChange={(e) => changeSpeed(parseFloat(e.target.value))}
              title="Playback Speed"
              aria-label="Playback speed"
            >
              {speeds.map((s) => (
                <option key={s} value={s}>
                  {s}x
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
