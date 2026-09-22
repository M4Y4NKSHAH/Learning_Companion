import React from 'react';
import { BookOpen, Layers, CheckCircle, ChevronRight, Sparkles } from 'lucide-react';

export default function ChapterNav({
  chapters = [],
  activeChapterIndex = null,
  onSelectChapter,
  activeColor = 'ember',
}) {
  if (!chapters || chapters.length <= 1) return null;

  return (
    <div className="glass-panel p-3 rounded-2xl mb-5 border border-sand-800">
      <div className="flex items-center justify-between mb-2.5 px-1">
        <div className="flex items-center gap-2">
          <Layers className={`w-4 h-4 text-${activeColor}-400`} />
          <span className="text-[11px] font-bold uppercase tracking-wider text-sand-300">
            Curriculum Chapters ({chapters.length})
          </span>
        </div>
        {activeChapterIndex !== null && (
          <button
            onClick={() => onSelectChapter(null)}
            className="text-[10px] text-sand-400 hover:text-sand-200 transition font-medium underline underline-offset-2"
          >
            View All Chapters
          </button>
        )}
      </div>

      {/* Chapter Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 custom-scrollbar">
        <button
          onClick={() => onSelectChapter(null)}
          className={`flex-shrink-0 px-3 py-1.5 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
            activeChapterIndex === null
              ? 'bg-sand-200 text-sand-900 shadow-md font-bold'
              : 'bg-sand-800/80 text-sand-400 hover:text-sand-200 hover:bg-sand-800'
          }`}
        >
          <BookOpen className="w-3 h-3" />
          <span>Complete Course</span>
        </button>

        {chapters.map((ch, idx) => {
          const isSelected = activeChapterIndex === idx;
          const chNum = ch.chapter_index || idx + 1;
          const title = ch.title || `Chapter ${chNum}`;

          return (
            <button
              key={ch.chapter_id || idx}
              onClick={() => onSelectChapter(idx)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 border ${
                isSelected
                  ? 'bg-clay-600 border-clay-500 text-white shadow-md shadow-sand-300/25'
                  : 'bg-sand-900/60 border-sand-800 text-sand-300 hover:text-sand-50 hover:border-sand-700'
              }`}
            >
              <span className="text-[10px] opacity-75 font-mono">Ch.{chNum}</span>
              <span className="max-w-[140px] truncate">{title}</span>
            </button>
          );
        })}
      </div>

      {/* Selected Chapter Quick Preview */}
      {activeChapterIndex !== null && chapters[activeChapterIndex] && (
        <div className="mt-2.5 pt-2.5 border-t border-sand-800/80 px-1 text-xs text-sand-300 flex items-start gap-2 animate-fadeIn">
          <Sparkles className="w-3.5 h-3.5 text-clay-400 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-sand-50">
              {chapters[activeChapterIndex].title}:{' '}
            </span>
            <span className="text-sand-400">
              {chapters[activeChapterIndex].summary || 'Structured theory and practice module.'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
