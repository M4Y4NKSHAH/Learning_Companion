import React, { useRef, useState, useEffect } from 'react';
import { BookOpen, Layers, CheckCircle, ChevronLeft, ChevronRight, Sparkles, Compass } from 'lucide-react';

const COLOR_MAP = {
  clay: { text: 'text-clay-400', bg: 'bg-clay-600', border: 'border-clay-500', badge: 'bg-clay-500/20 text-clay-300 border-clay-500/30' },
  ember: { text: 'text-ember-400', bg: 'bg-ember-600', border: 'border-ember-500', badge: 'bg-ember-500/20 text-ember-300 border-ember-500/30' },
  olive: { text: 'text-olive-400', bg: 'bg-olive-600', border: 'border-olive-500', badge: 'bg-olive-500/20 text-olive-300 border-olive-500/30' },
};

function formatCleanChapterTitle(title, chNum) {
  if (!title) return `Chapter ${chNum}`;
  // Strip leading numbering like "1. ", "Chapter 1: ", etc. to prevent duplicate numbering
  return title
    .replace(/^(?:chapter|ch\.?)\s*\d+[:.\s-]*/i, '')
    .replace(/^\d+[\.\s\-:]+/, '')
    .trim() || title;
}

export default function ChapterNav({
  chapters = [],
  activeChapterIndex = null,
  onSelectChapter,
  activeColor = 'clay',
}) {
  const scrollRef = useRef(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const colors = COLOR_MAP[activeColor] || COLOR_MAP.clay;

  const checkScroll = () => {
    if (!scrollRef.current) return;
    const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
    setCanScrollLeft(scrollLeft > 4);
    setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 4);
  };

  useEffect(() => {
    checkScroll();
    window.addEventListener('resize', checkScroll);
    return () => window.removeEventListener('resize', checkScroll);
  }, [chapters]);

  const handleScroll = (offset) => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: offset, behavior: 'smooth' });
      setTimeout(checkScroll, 200);
    }
  };

  if (!chapters || chapters.length <= 1) return null;

  const activeChapter = activeChapterIndex !== null ? chapters[activeChapterIndex] : null;

  return (
    <div className="glass-panel p-3.5 sm:p-4 rounded-2xl mb-5 border border-sand-800 shadow-xl relative transition-all">
      {/* Header bar */}
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-sand-900 border border-sand-800">
            <Layers className={`w-3.5 h-3.5 ${colors.text}`} />
          </div>
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-sand-200">
              Curriculum Chapters
            </span>
            <span className="text-[10px] font-mono text-sand-400 ml-1.5">
              ({chapters.length} total)
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {activeChapterIndex !== null && (
            <button
              onClick={() => onSelectChapter(null)}
              className="text-[10px] text-sand-400 hover:text-sand-100 transition font-medium px-2 py-0.5 rounded-lg hover:bg-sand-900 border border-transparent hover:border-sand-800"
            >
              Reset to All
            </button>
          )}

          {/* Scroll navigation arrows for long chapter lists */}
          <div className="hidden sm:flex items-center gap-1">
            <button
              onClick={() => handleScroll(-220)}
              disabled={!canScrollLeft}
              className="p-1 rounded-lg bg-sand-900 border border-sand-800 text-sand-400 hover:text-sand-100 disabled:opacity-25 disabled:cursor-not-allowed transition"
              title="Scroll left"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => handleScroll(220)}
              disabled={!canScrollRight}
              className="p-1 rounded-lg bg-sand-900 border border-sand-800 text-sand-400 hover:text-sand-100 disabled:opacity-25 disabled:cursor-not-allowed transition"
              title="Scroll right"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Chapter Pills Carousel */}
      <div
        ref={scrollRef}
        onScroll={checkScroll}
        className="flex items-center gap-2 overflow-x-auto pb-1.5 pt-0.5 custom-scrollbar scroll-smooth"
      >
        <button
          onClick={() => onSelectChapter(null)}
          className={`flex-shrink-0 px-3.5 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 border ${
            activeChapterIndex === null
              ? 'bg-sand-100 text-sand-950 font-bold border-sand-100 shadow-md'
              : 'bg-sand-900/60 border-sand-800 text-sand-300 hover:text-sand-50 hover:bg-sand-900 hover:border-sand-700'
          }`}
        >
          <Compass className="w-3.5 h-3.5" />
          <span>Full Course</span>
        </button>

        {chapters.map((ch, idx) => {
          const isSelected = activeChapterIndex === idx;
          const chNum = ch.chapter_index || idx + 1;
          const cleanTitle = formatCleanChapterTitle(ch.title, chNum);

          return (
            <button
              key={ch.chapter_id || idx}
              onClick={() => onSelectChapter(idx)}
              title={ch.title || `Chapter ${chNum}`}
              className={`flex-shrink-0 px-3.5 py-2 rounded-xl text-xs font-medium transition flex items-center gap-2 border ${
                isSelected
                  ? `${colors.bg} ${colors.border} text-white shadow-lg shadow-sand-300/25 font-bold ring-1 ring-white/20`
                  : 'bg-sand-900/70 border-sand-800 text-sand-300 hover:text-sand-50 hover:bg-sand-900 hover:border-sand-700'
              }`}
            >
              <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                isSelected ? 'bg-black/25 text-white' : 'bg-sand-950 text-sand-400 border border-sand-800'
              }`}>
                §{chNum}
              </span>
              <span className="max-w-[160px] truncate">{cleanTitle}</span>
            </button>
          );
        })}
      </div>

      {/* Selected Chapter Quick Preview */}
      {activeChapter && (
        <div className="mt-3 pt-3 border-t border-sand-800/80 px-1 text-xs text-sand-300 flex items-start justify-between gap-3 animate-fadeIn">
          <div className="flex items-start gap-2.5 flex-1 min-w-0">
            <Sparkles className={`w-3.5 h-3.5 ${colors.text} shrink-0 mt-0.5`} />
            <div className="min-w-0">
              <span className="font-bold text-sand-100 mr-1.5">
                {activeChapter.title}:
              </span>
              <span className="text-sand-400 text-[11px] leading-relaxed line-clamp-1">
                {activeChapter.summary || 'Structured theory and practice module.'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0 font-mono text-[10px] text-sand-400">
            {activeChapter.sections_count ? (
              <span className="px-2 py-0.5 rounded bg-sand-950 border border-sand-800">
                {activeChapter.sections_count} Sections
              </span>
            ) : null}
            {activeChapter.cards?.length ? (
              <span className="px-2 py-0.5 rounded bg-sand-950 border border-sand-800">
                {activeChapter.cards.length} Cards
              </span>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
