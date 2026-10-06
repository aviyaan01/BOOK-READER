import React, { useState, useEffect } from 'react';
import { Sparkles, BookOpen } from 'lucide-react';
import BookUploader from '../components/BookUploader';
import UploadProgressTracker from '../components/UploadProgressTracker';
import BookList from '../components/BookList';
import ErrorMessageBox from '../components/ErrorMessageBox';
import { fetchBooks } from '../api';

export default function HomePage() {
  const [books, setBooks] = useState([]);
  const [loadingBooks, setLoadingBooks] = useState(true);
  const [activeUploadBookId, setActiveUploadBookId] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  // Load previously uploaded books on mount
  useEffect(() => {
    loadBooks();
  }, []);

  const loadBooks = async () => {
    try {
      setLoadingBooks(true);
      const data = await fetchBooks();
      setBooks(data || []);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load books from server.');
    } finally {
      setLoadingBooks(false);
    }
  };

  const handleUploadSuccess = (result) => {
    if (result && result.id) {
      setActiveUploadBookId(result.id);
      loadBooks();
    }
  };

  const handleBookDeleted = (deletedId) => {
    setBooks((prev) => prev.filter((b) => b.id !== deletedId));
    if (activeUploadBookId === deletedId) {
      setActiveUploadBookId(null);
    }
  };

  const handleProgressChange = (updatedBook) => {
    setBooks((prev) =>
      prev.map((b) => (b.id === updatedBook.id ? { ...b, ...updatedBook } : b))
    );
  };

  return (
    <div className="home-page-container" style={{ padding: '24px 16px 60px' }}>
      {/* Hero Header */}
      <div className="hero-banner">
        <div className="hero-pill">
          <Sparkles size={14} />
          <span>Expressive Neural Storyteller</span>
        </div>
        <h1 className="hero-title">
          Bring Your Storybooks to Life
        </h1>
        <p className="hero-subtitle">
          Upload any <strong>Bangla (বাংলা)</strong> or <strong>English</strong> PDF storybook.
          Narrated in expressive storyteller voices with real-time word read-along.
        </p>
      </div>

      {/* Visible Error Message Box */}
      <div style={{ maxWidth: '720px', margin: '0 auto' }}>
        <ErrorMessageBox error={errorMessage} onDismiss={() => setErrorMessage(null)} />
      </div>

      {/* Upload Box */}
      <BookUploader
        onUploadSuccess={handleUploadSuccess}
        onError={(msg) => setErrorMessage(msg)}
      />

      {/* Real-time Narration Progress for actively uploaded book */}
      {activeUploadBookId && (
        <UploadProgressTracker
          bookId={activeUploadBookId}
          onStatusChange={handleProgressChange}
          onError={(msg) => setErrorMessage(msg)}
        />
      )}

      {/* Library of previously uploaded books */}
      <BookList
        books={books}
        onBookDeleted={handleBookDeleted}
        onBookUpdated={loadBooks}
        loading={loadingBooks}
        onError={(msg) => setErrorMessage(msg)}
      />
    </div>
  );
}
