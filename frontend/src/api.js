/**
 * API service for communicating with the PDF Storyteller FastAPI backend.
 * Uses VITE_API_URL from environment variables (.env).
 */

export const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');

/**
 * Fetch list of all uploaded books.
 */
export async function fetchBooks() {
  const res = await fetch(`${BASE_URL}/api/books`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to fetch books');
  }
  return res.json();
}

/**
 * Fetch book details and narration progress by book ID.
 */
export async function fetchBook(bookId) {
  const res = await fetch(`${BASE_URL}/api/books/${bookId}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch book '${bookId}'`);
  }
  return res.json();
}

/**
 * Fetch ordered chunks for a book.
 */
export async function fetchBookChunks(bookId) {
  const res = await fetch(`${BASE_URL}/api/books/${bookId}/chunks`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch chunks for book '${bookId}'`);
  }
  return res.json();
}

/**
 * Upload a PDF file to create a Book row and trigger background narration.
 *
 * @param {File} file - PDF file (max 30MB)
 * @param {string} language - "bn" or "en"
 * @param {string} [voice] - Optional voice name
 * @returns {Promise<{id: string, status: string}>}
 */
export async function uploadBookPdf(file, language = 'en', voice = '') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('language', language);
  if (voice && voice.trim()) {
    formData.append('voice', voice.trim());
  }

  const res = await fetch(`${BASE_URL}/api/books`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to upload PDF storybook');
  }
  return res.json();
}

/**
 * Delete a book, its database records, and all storage audio files.
 */
export async function deleteBook(bookId) {
  const res = await fetch(`${BASE_URL}/api/books/${bookId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to delete book');
  }
  return res.json();
}

/**
 * Fetch available TTS voices optionally filtered by language ("bn" or "en").
 */
export async function fetchVoices(language = null) {
  const query = language ? `?language=${encodeURIComponent(language)}` : '';
  const res = await fetch(`${BASE_URL}/api/voices${query}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to fetch TTS voices');
  }
  return res.json();
}

/**
 * Format full audio URL for a chunk audio path.
 */
export function getFullAudioUrl(audioUrl) {
  if (!audioUrl) return null;
  if (audioUrl.startsWith('http://') || audioUrl.startsWith('https://')) {
    return audioUrl;
  }
  return `${BASE_URL}${audioUrl.startsWith('/') ? '' : '/'}${audioUrl}`;
}
