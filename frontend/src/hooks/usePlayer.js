import { useState, useEffect, useRef, useCallback } from 'react';
import { getFullAudioUrl } from '../api';

const SPEEDS = [0.75, 1.0, 1.25, 1.5, 2.0];
const SAVE_INTERVAL_MS = 2500;

/**
 * Custom audio player hook for PDF Storyteller.
 *
 * Features:
 * - Sequential chunk playback with zero gap (preloads next chunk)
 * - Play / Pause / Previous / Next / Skip back 10s
 * - Playback rate control (0.75x, 1x, 1.25x, 1.5x, 2x)
 * - Auto-resume & localStorage position saving
 * - Media Session API integration for lock-screen & headphone controls
 * - Waiting for generation state when playback hits an unfinished chunk
 *
 * @param {string} bookId - Unique book identifier
 * @param {Object} book - Book metadata object
 * @param {Array} chunks - Ordered list of chunk objects
 * @returns {Object} Player state and controls
 */
export function usePlayer(bookId, book, chunks = []) {
  const [activeChunkIndex, setActiveChunkIndex] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [isWaitingForGeneration, setIsWaitingForGeneration] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);

  // Audio elements: primary audio player and background preloader
  const currentAudioRef = useRef(null);
  const preloadAudioRef = useRef(null);

  // References to keep callbacks current without re-attaching listeners
  const activeChunkIndexRef = useRef(activeChunkIndex);
  activeChunkIndexRef.current = activeChunkIndex;

  const isPlayingRef = useRef(isPlaying);
  isPlayingRef.current = isPlaying;

  const playbackSpeedRef = useRef(playbackSpeed);
  playbackSpeedRef.current = playbackSpeed;

  const chunksRef = useRef(chunks);
  chunksRef.current = chunks;

  const isWaitingRef = useRef(isWaitingForGeneration);
  isWaitingRef.current = isWaitingForGeneration;

  const lastSaveTimeRef = useRef(0);

  // 1. Initialize Audio instances
  useEffect(() => {
    const audio = new Audio();
    audio.preload = 'auto';
    currentAudioRef.current = audio;

    const preloader = new Audio();
    preloader.preload = 'auto';
    preloadAudioRef.current = preloader;

    // Time update handler
    const handleTimeUpdate = () => {
      if (!currentAudioRef.current) return;
      const cur = currentAudioRef.current.currentTime || 0;
      const dur = currentAudioRef.current.duration || 0;
      setCurrentTime(cur);
      setDuration(dur);

      // Periodically persist playback position to localStorage
      const now = Date.now();
      if (now - lastSaveTimeRef.current > SAVE_INTERVAL_MS && activeChunkIndexRef.current !== null) {
        lastSaveTimeRef.current = now;
        savePosition(bookId, activeChunkIndexRef.current, cur);
      }

      // Update MediaSession position state if supported
      updateMediaSessionPosition(cur, dur, playbackSpeedRef.current);
    };

    // Metadata loaded
    const handleLoadedMetadata = () => {
      if (currentAudioRef.current) {
        setDuration(currentAudioRef.current.duration || 0);
      }
    };

    // Chunk playback ended -> seamless transition to next chunk
    const handleEnded = () => {
      const curIndex = activeChunkIndexRef.current;
      const currentList = chunksRef.current;
      const nextIndex = curIndex + 1;
      const nextChunk = currentList.find((c) => c.index === nextIndex);

      if (nextChunk) {
        if (nextChunk.status === 'done' && nextChunk.audio_url) {
          // Play next chunk immediately with zero gap
          playChunk(nextIndex, 0);
        } else {
          // Chunk is still generating in background!
          setActiveChunkIndex(nextIndex);
          setIsWaitingForGeneration(true);
          setIsPlaying(true); // Maintain intent to play
          if (currentAudioRef.current) {
            currentAudioRef.current.pause();
          }
        }
      } else {
        // End of story
        setIsPlaying(false);
        setCurrentTime(0);
        savePosition(bookId, curIndex, 0);
      }
    };

    const handleError = (e) => {
      console.warn('Audio playback error:', e);
    };

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);

    return () => {
      audio.pause();
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
      currentAudioRef.current = null;
      preloadAudioRef.current = null;
    };
  }, [bookId]);

  // 2. Restore saved position from localStorage on initial load
  useEffect(() => {
    if (hasInitialized || chunks.length === 0) return;

    const saved = loadSavedPosition(bookId);
    if (saved && saved.chunkIndex) {
      const target = chunks.find((c) => c.index === saved.chunkIndex);
      if (target) {
        setActiveChunkIndex(target.index);
        setCurrentTime(saved.currentTime || 0);
        // Preload target chunk audio
        if (target.status === 'done' && target.audio_url && currentAudioRef.current) {
          const url = getFullAudioUrl(target.audio_url);
          currentAudioRef.current.src = url;
          currentAudioRef.current.currentTime = saved.currentTime || 0;
        }
        setHasInitialized(true);
        return;
      }
    }

    // Default to first done chunk, or first chunk
    const firstDone = chunks.find((c) => c.status === 'done') || chunks[0];
    if (firstDone) {
      setActiveChunkIndex(firstDone.index);
      if (firstDone.status === 'done' && firstDone.audio_url && currentAudioRef.current) {
        currentAudioRef.current.src = getFullAudioUrl(firstDone.audio_url);
      }
    }
    setHasInitialized(true);
  }, [bookId, chunks, hasInitialized]);

  // 3. React when chunks update: if we were waiting for generation and it's now ready, auto-play!
  useEffect(() => {
    if (!isWaitingForGeneration || activeChunkIndex === null) return;

    const targetChunk = chunks.find((c) => c.index === activeChunkIndex);
    if (targetChunk && targetChunk.status === 'done' && targetChunk.audio_url) {
      setIsWaitingForGeneration(false);
      playChunk(targetChunk.index, 0);
    }
  }, [chunks, isWaitingForGeneration, activeChunkIndex]);

  // 4. Preload next chunk whenever activeChunkIndex changes
  useEffect(() => {
    if (activeChunkIndex === null || chunks.length === 0) return;

    const nextChunk = chunks.find((c) => c.index === activeChunkIndex + 1);
    if (nextChunk && nextChunk.status === 'done' && nextChunk.audio_url) {
      const nextUrl = getFullAudioUrl(nextChunk.audio_url);
      if (preloadAudioRef.current) {
        preloadAudioRef.current.src = nextUrl;
        preloadAudioRef.current.load();
      }
    }
  }, [activeChunkIndex, chunks]);

  // Helper: Save position to localStorage
  const savePosition = (bId, chunkIdx, timeSec) => {
    try {
      localStorage.setItem(
        `storyteller_playback_${bId}`,
        JSON.stringify({
          chunkIndex: chunkIdx,
          currentTime: Math.round(timeSec * 10) / 10,
          updatedAt: Date.now(),
        })
      );
    } catch {
      // Ignore localStorage errors (e.g. incognito)
    }
  };

  // Helper: Load saved position
  const loadSavedPosition = (bId) => {
    try {
      const raw = localStorage.getItem(`storyteller_playback_${bId}`);
      if (raw) return JSON.parse(raw);
    } catch {
      return null;
    }
    return null;
  };

  // 5. Play a specific chunk
  const playChunk = useCallback(
    (chunkIndex, startAtTime = 0) => {
      const audio = currentAudioRef.current;
      if (!audio) return;

      const target = chunksRef.current.find((c) => c.index === chunkIndex);
      if (!target) return;

      setActiveChunkIndex(chunkIndex);

      if (target.status !== 'done' || !target.audio_url) {
        // Not ready yet -> enter waiting for generation
        setIsWaitingForGeneration(true);
        setIsPlaying(true);
        audio.pause();
        return;
      }

      setIsWaitingForGeneration(false);
      const url = getFullAudioUrl(target.audio_url);

      // Check if preloadAudioRef already has this exact source
      if (preloadAudioRef.current && preloadAudioRef.current.src === url) {
        audio.src = url;
      } else if (audio.src !== url) {
        audio.src = url;
      }

      audio.playbackRate = playbackSpeedRef.current;

      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            if (startAtTime > 0) {
              audio.currentTime = startAtTime;
            }
            setIsPlaying(true);
            savePosition(bookId, chunkIndex, startAtTime);
          })
          .catch((err) => {
            console.log('Play interrupted or failed:', err);
            setIsPlaying(false);
          });
      }
    },
    [bookId]
  );

  // Play / Resume
  const play = useCallback(() => {
    const audio = currentAudioRef.current;
    if (!audio) return;

    if (activeChunkIndexRef.current === null) {
      const first = chunksRef.current[0];
      if (first) playChunk(first.index, 0);
      return;
    }

    const currentChunk = chunksRef.current.find((c) => c.index === activeChunkIndexRef.current);
    if (currentChunk && (currentChunk.status !== 'done' || !currentChunk.audio_url)) {
      setIsWaitingForGeneration(true);
      setIsPlaying(true);
      return;
    }

    audio.playbackRate = playbackSpeedRef.current;
    audio
      .play()
      .then(() => {
        setIsPlaying(true);
        setIsWaitingForGeneration(false);
      })
      .catch((err) => console.log('Resume playback failed:', err));
  }, [playChunk]);

  // Pause
  const pause = useCallback(() => {
    const audio = currentAudioRef.current;
    if (audio) {
      audio.pause();
    }
    setIsPlaying(false);
    setIsWaitingForGeneration(false);
    if (activeChunkIndexRef.current !== null && audio) {
      savePosition(bookId, activeChunkIndexRef.current, audio.currentTime);
    }
  }, [bookId]);

  // Toggle play/pause
  const togglePlay = useCallback(() => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  }, [isPlaying, play, pause]);

  // Previous chunk
  const prevChunk = useCallback(() => {
    const cur = activeChunkIndexRef.current;
    if (cur === null) return;
    const prev = [...chunksRef.current].reverse().find((c) => c.index < cur && c.status === 'done');
    if (prev) {
      playChunk(prev.index, 0);
    } else {
      // Seek to beginning of current chunk
      seekTo(0);
    }
  }, [playChunk, seekTo]);

  // Next chunk
  const nextChunk = useCallback(() => {
    const cur = activeChunkIndexRef.current;
    if (cur === null) return;
    const next = chunksRef.current.find((c) => c.index > cur);
    if (next) {
      playChunk(next.index, 0);
    }
  }, [playChunk]);

  // Skip back 10 seconds
  const skipBack = useCallback(
    (seconds = 10) => {
      const audio = currentAudioRef.current;
      if (!audio) return;
      const targetTime = Math.max(0, audio.currentTime - seconds);
      audio.currentTime = targetTime;
      setCurrentTime(targetTime);
      if (activeChunkIndexRef.current !== null) {
        savePosition(bookId, activeChunkIndexRef.current, targetTime);
      }
    },
    [bookId]
  );

  // Seek to specific time within current chunk
  const seekTo = useCallback(
    (targetTime) => {
      const audio = currentAudioRef.current;
      if (!audio) return;
      audio.currentTime = targetTime;
      setCurrentTime(targetTime);
      if (activeChunkIndexRef.current !== null) {
        savePosition(bookId, activeChunkIndexRef.current, targetTime);
      }
    },
    [bookId]
  );

  // Change playback speed
  const changeSpeed = useCallback((speed) => {
    setPlaybackSpeed(speed);
    if (currentAudioRef.current) {
      currentAudioRef.current.playbackRate = speed;
    }
  }, []);

  // 6. Media Session API Integration
  useEffect(() => {
    if (!('mediaSession' in navigator) || activeChunkIndex === null) return;

    const currentChunk = chunks.find((c) => c.index === activeChunkIndex);
    const chunkTitle = currentChunk?.text
      ? currentChunk.text.length > 55
        ? `${currentChunk.text.slice(0, 55)}...`
        : currentChunk.text
      : `Sentence #${activeChunkIndex}`;

    // Set lock-screen metadata
    try {
      navigator.mediaSession.metadata = new window.MediaMetadata({
        title: chunkTitle,
        artist: book?.voice || 'PDF Storyteller',
        album: book?.title || 'Storybook Audiobook',
        artwork: [
          {
            src: '/favicon.svg',
            sizes: '96x96',
            type: 'image/svg+xml',
          },
        ],
      });
    } catch {
      // Older browsers may fail MediaMetadata instantiation
    }

    // Set lockscreen & headphone action handlers
    const actionHandlers = [
      ['play', play],
      ['pause', pause],
      ['previoustrack', prevChunk],
      ['nexttrack', nextChunk],
      ['seekbackward', (details) => skipBack(details.seekOffset || 10)],
      ['seekforward', (details) => seekTo((currentAudioRef.current?.currentTime || 0) + (details.seekOffset || 10))],
      ['seekto', (details) => seekTo(details.seekTime)],
    ];

    for (const [action, handler] of actionHandlers) {
      try {
        navigator.mediaSession.setActionHandler(action, handler);
      } catch {
        // Not all actions supported on all platforms
      }
    }

    navigator.mediaSession.playbackState = isPlaying ? 'playing' : 'paused';

    return () => {
      for (const [action] of actionHandlers) {
        try {
          navigator.mediaSession.setActionHandler(action, null);
        } catch {}
      }
    };
  }, [activeChunkIndex, isPlaying, book?.title, book?.voice, chunks, play, pause, prevChunk, nextChunk, skipBack, seekTo]);

  // Helper to update MediaSession position state
  const updateMediaSessionPosition = (pos, dur, rate) => {
    if ('mediaSession' in navigator && navigator.mediaSession.setPositionState && dur > 0) {
      try {
        navigator.mediaSession.setPositionState({
          duration: Math.max(dur, 0.1),
          playbackRate: rate,
          position: Math.min(pos, dur),
        });
      } catch {
        // Ignore position state sync glitches
      }
    }
  };

  const currentChunk = chunks.find((c) => c.index === activeChunkIndex) || null;

  return {
    activeChunkIndex,
    currentChunk,
    isPlaying,
    currentTime,
    duration,
    playbackSpeed,
    speeds: SPEEDS,
    isWaitingForGeneration,
    play,
    pause,
    togglePlay,
    playChunk,
    nextChunk,
    prevChunk,
    skipBack,
    seekTo,
    changeSpeed,
  };
}
