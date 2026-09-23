import React, { useEffect, useState } from 'react';
import { CheckCircle, ArrowRight, X } from 'lucide-react';

/**
 * Welcome-back overlay for when an already-authenticated user lands on the
 * marketing page (initial load, or after tapping "Return to Landing Page").
 *
 * Japandi soft entrance: backdrop fades in, card slides up, then auto-advances
 * to the dashboard after a short pause — or immediately on tap.
 */
export default function WelcomeBackModal({ user, onProceed }) {
  const [visible, setVisible] = useState(false);
  const [showButton, setShowButton] = useState(false);

  useEffect(() => {
    const t1 = setTimeout(() => setVisible(true), 120);
    const t2 = setTimeout(() => setShowButton(true), 900);
    const t3 = setTimeout(() => onProceed(), 2000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [onProceed]);

  return (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center p-4 bg-sand-50/65 backdrop-blur-sm animate-fadeIn"
      onClick={onProceed}
    >
      <div
        className={`relative w-full max-w-sm glass-panel border border-sand-800 rounded-2xl shadow-japandi-lg transition-all duration-500 ${
          visible ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-6 scale-95'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close (X) — stays on landing, CTAs will re-trigger */}
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onProceed(); }}
          className="absolute top-3 right-3 p-1 rounded-lg text-sand-400 hover:text-sand-50 hover:bg-sand-900/60 transition-colors"
          aria-label="Close"
        >
          <BookmarkOrClose />
        </button>

        <div className="p-6 text-center">
          <div
            className={`mx-auto mb-4 w-14 h-14 rounded-full bg-olive-500/10 border border-olive-500/30 flex items-center justify-center transition-opacity duration-300 ${
              visible ? 'opacity-100' : 'opacity-0'
            }`}
          >
            <CheckCircle className="w-7 h-7 text-olive-500" />
          </div>

          <h2 className="text-lg font-bold text-sand-50 mb-1">
            Welcome back, {user?.name || 'learner'}
          </h2>
          <p className="text-xs text-sand-400 mb-5 leading-relaxed">
            Your session is active. Taking you to the workspace…
          </p>

          {showButton && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onProceed(); }}
              className="w-full bg-olive-600 hover:bg-olive-500 text-white text-xs font-bold py-2.5 rounded-xl shadow-lg shadow-sand-300/25 transition-all flex items-center justify-center gap-2 active:scale-[0.98]"
            >
              Go to Dashboard
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/** Small reusable X icon styled for the welcome overlay */
function BookmarkOrClose() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-4 h-4"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
