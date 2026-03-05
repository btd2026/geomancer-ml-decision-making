import { useEffect, useState } from 'react';

const ImageModal = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [imageSrc, setImageSrc] = useState('');

  useEffect(() => {
    // Listen for global modal events (for compatibility with existing code)
    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');

    if (modal && modalImage) {
      // Override the modal behavior
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.attributeName === 'class') {
            const hasOpen = modal.classList.contains('open');
            setIsOpen(hasOpen);
            if (hasOpen) {
              setImageSrc(modalImage.src);
            }
          }
        });
      });

      observer.observe(modal, { attributes: true });

      return () => observer.disconnect();
    }
  }, []);

  const closeModal = () => {
    setIsOpen(false);
    // Also update the DOM element for compatibility
    const modal = document.getElementById('imageModal');
    if (modal) {
      modal.classList.remove('open');
    }
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      closeModal();
    }
  };

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        closeModal();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  return (
    <>
      {/* Hidden modal element for compatibility with existing code */}
      <div id="imageModal" className={`image-modal ${isOpen ? 'open' : ''}`} style={{ display: 'none' }}>
        <img id="modalImage" src={imageSrc} alt="PHATE visualization" />
      </div>

      {/* React modal implementation */}
      {isOpen && (
        <div
          className="image-modal open"
          onClick={handleBackdropClick}
          style={{
            display: 'flex',
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: 'rgba(0,0,0,0.9)',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <span
            className="modal-close"
            onClick={closeModal}
            style={{
              position: 'absolute',
              top: '20px',
              right: '30px',
              color: 'white',
              fontSize: '36px',
              cursor: 'pointer'
            }}
          >
            &times;
          </span>
          <img
            src={imageSrc}
            alt="PHATE visualization"
            style={{
              maxWidth: '90%',
              maxHeight: '90%'
            }}
          />
        </div>
      )}
    </>
  );
};

export default ImageModal;
