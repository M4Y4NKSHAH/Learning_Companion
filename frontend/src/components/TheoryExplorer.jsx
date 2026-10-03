import React, { useState, useMemo, useEffect } from 'react';
import { 
  BookOpen, 
  Sparkles, 
  Layers, 
  ArrowRight, 
  ChevronRight, 
  ChevronDown,
  ChevronLeft,
  Lightbulb, 
  AlertTriangle, 
  CheckCircle2, 
  FileText, 
  Atom,
  Binary,
  HelpCircle,
  Copy,
  Check,
  RotateCcw,
  Compass,
  Maximize2,
  Minimize2
} from 'lucide-react';
import ChapterNav from './ChapterNav';

const COLOR_MAP = {
  clay: {
    text: 'text-clay-400',
    bg: 'bg-clay-600',
    border: 'border-clay-500/40',
    badge: 'bg-clay-500/20 text-clay-300 border-clay-500/30',
    ring: 'ring-clay-500/40',
    gradient: 'from-clay-600 via-amber-600 to-ember-600'
  },
  ember: {
    text: 'text-ember-400',
    bg: 'bg-ember-600',
    border: 'border-ember-500/40',
    badge: 'bg-ember-500/20 text-ember-300 border-ember-500/30',
    ring: 'ring-ember-500/40',
    gradient: 'from-ember-600 via-clay-600 to-amber-600'
  },
  olive: {
    text: 'text-olive-400',
    bg: 'bg-olive-600',
    border: 'border-olive-500/40',
    badge: 'bg-olive-500/20 text-olive-300 border-olive-500/30',
    ring: 'ring-olive-500/40',
    gradient: 'from-olive-600 via-clay-600 to-amber-600'
  },
};

/** Formats inline markdown bold and code ticks cleanly */
function formatInlineProse(text) {
  if (!text) return null;
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-sand-100">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="px-1.5 py-0.5 rounded bg-sand-900 border border-sand-800 text-clay-300 font-mono text-[11px]">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

/**
 * Renders raw chapter source text as clean readable prose.
 * Converts ### headings to warm styled headers, supports lists and equations.
 */
function renderSourceAsProse(rawText) {
  if (!rawText) return null;
  const blocks = rawText.split(/\n\s*\n/).map(b => b.trim()).filter(Boolean);

  return blocks.map((block, i) => {
    // Detect markdown headings (# ## ### ####)
    const headingMatch = block.match(/^(#{1,4})\s+(.+)/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const title = headingMatch[2].replace(/^[\d.]+\s*/, '').trim();
      if (!title) return null;
      const sizeClass = level <= 2 ? 'text-base font-extrabold text-ember-300' : 'text-sm font-bold text-clay-300';
      return (
        <h4
          key={i}
          className={`${sizeClass} border-b border-sand-800 pb-1 mt-6 mb-2 tracking-tight`}
        >
          {title}
        </h4>
      );
    }

    // Detect numbered section headings like "1.1 Title of Section"
    const sectionMatch = block.match(/^([1-9]\d*\.[0-9]+)\s+([A-Z].{2,})/);
    if (sectionMatch && block.length < 120) {
      const label = sectionMatch[1];
      const title = sectionMatch[2].trim();
      return (
        <h4 key={i} className="text-sm font-bold text-clay-300 border-b border-sand-800/60 pb-1 mt-5 mb-2 tracking-tight flex items-center gap-2">
          <span className="font-mono text-sand-500 text-xs px-1.5 py-0.5 rounded bg-sand-900 border border-sand-800">{label}</span>
          <span>{title}</span>
        </h4>
      );
    }

    // Detect bulleted or numbered list items inside block
    const lines = block.split('\n');
    const isList = lines.length > 1 && lines.every(ln => /^[-*•]\s+/.test(ln.trim()) || /^\d+\.\s+/.test(ln.trim()));
    if (isList) {
      return (
        <ul key={i} className="space-y-1.5 my-3 pl-4 list-disc text-sand-300 text-xs sm:text-sm">
          {lines.map((ln, lineIdx) => {
            const cleanLn = ln.replace(/^[-*•\d.]+\s+/, '').trim();
            return <li key={lineIdx} className="leading-relaxed">{formatInlineProse(cleanLn)}</li>;
          })}
        </ul>
      );
    }

    // Detect isolated equations
    if (block.includes('=') && block.length < 90 && !block.includes('.')) {
      return (
        <div key={i} className="my-3 px-4 py-2.5 rounded-xl bg-sand-950 border border-clay-500/20 text-center font-mono text-xs sm:text-sm text-clay-200">
          {block}
        </div>
      );
    }

    // Regular prose paragraph
    const clean = block.replace(/^[#\s]+/, '').trim();
    if (!clean) return null;
    return (
      <p key={i} className="text-xs sm:text-sm text-sand-300 leading-relaxed mb-3">
        {formatInlineProse(clean)}
      </p>
    );
  });
}

export default function TheoryExplorer({
  courseTitle = 'Curriculum Theory',
  chapters = [],
  activeChapterIndex = null,
  onSelectChapter,
  onNavigateToPractice,
  cards = [],
  activeColor = 'clay'
}) {
  const [viewMode, setViewMode] = useState('reader'); // 'reader' | 'matrix' | 'cards'
  const [expandedSection, setExpandedSection] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [cardIndex, setCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [showFullSource, setShowFullSource] = useState(false);
  const [openSection, setOpenSection] = useState(null);
  const [expandAllSections, setExpandAllSections] = useState(false);

  const colors = COLOR_MAP[activeColor] || COLOR_MAP.clay;

  const currentChapterIndex = activeChapterIndex !== null ? activeChapterIndex : 0;
  const currentChapter = chapters[currentChapterIndex] || (chapters.length > 0 ? chapters[0] : null);

  const displayedCards = (currentChapter?.cards?.length > 0)
    ? currentChapter.cards
    : cards;

  const deepTheory = currentChapter?.deep_theory || {};
  const principles = deepTheory.principles || [
    {
      title: "Foundational Governing Law",
      content: currentChapter?.summary || "Core theoretical relationships and state definitions.",
      tag: "Core Axiom"
    }
  ];
  const formulations = deepTheory.formulations || [
    {
      title: "Analytical Formulation & State Invariants",
      formula: "Governing equations establishing system behavior",
      derivation: "Derived from fundamental axioms and boundary constraints.",
      variables: "State variables, proportionalities, and limiting conditions."
    }
  ];
  const mentalModels = deepTheory.mental_models || [
    {
      concept: "Intuitive Mental Model",
      analogy: `Think of ${currentChapter?.title || 'this system'} as an interconnected equilibrium where governing laws dictate the state trajectory.`,
      takeaway: "Always check what is conserved and what boundary conditions apply."
    }
  ];
  const misconceptions = deepTheory.misconceptions || [
    {
      trap: "Superficial Formula Application Without Verifying Operational Domain",
      correction: "Always isolate state variables and confirm boundary assumptions before executing derivations or problem sets."
    }
  ];

  // Source-extracted glossary + worked examples attached by the book processor
  const keyTerms = Array.isArray(deepTheory.key_terms) ? deepTheory.key_terms : [];
  const workedExamples = Array.isArray(deepTheory.worked_examples) ? deepTheory.worked_examples : [];

  // Normalize objectives — can be strings or {objective: "..."} objects
  const rawObjectives = currentChapter?.objectives || [
    "Master fundamental definitions and mechanics",
    "Apply analytical formulations to problem solving",
    "Identify key boundary conditions and diagnostic traps"
  ];
  const objectives = rawObjectives.map(o => (typeof o === 'string' ? o : (o?.objective || o?.text || JSON.stringify(o))));

  // First mental model's analogy as a warm pull-quote hook
  const hookAnalogy = mentalModels[0]?.analogy || null;

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleChapterChange = (idx) => {
    onSelectChapter?.(idx);
    setCardIndex(0);
    setIsFlipped(false);
    setExpandedSection(null);
    setShowFullSource(false);
    setOpenSection(null);
    setExpandAllSections(false);
  };

  // Keyboard navigation for active deck view mode
  useEffect(() => {
    if (viewMode !== 'cards') return;
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'ArrowLeft') {
        setCardIndex((prev) => Math.max(0, prev - 1));
        setIsFlipped(false);
      } else if (e.key === 'ArrowRight') {
        setCardIndex((prev) => Math.min(displayedCards.length - 1, prev + 1));
        setIsFlipped(false);
      } else if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        setIsFlipped((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [viewMode, displayedCards.length]);

  const hasPrev = currentChapterIndex > 0;
  const hasNext = currentChapterIndex < chapters.length - 1;

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-fadeIn">
      {/* CHAPTER SELECTION PILL BAR */}
      {chapters.length > 1 && (
        <ChapterNav
          chapters={chapters}
          activeChapterIndex={currentChapterIndex}
          onSelectChapter={handleChapterChange}
          activeColor={activeColor}
        />
      )}

      {/* TOP HEADER CONTROLS */}
      <div className="glass-panel p-6 sm:p-7 rounded-3xl border border-sand-800 shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-5 transition-all">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider ${colors.badge}`}>
              Theory Explorer
            </span>
            <span className="text-sand-600">•</span>
            <span className="text-xs font-mono text-sand-400">
              {currentChapter ? `Chapter ${currentChapterIndex + 1} of ${chapters.length}` : courseTitle}
            </span>
            {currentChapter?.unit_name && (
              <>
                <span className="text-sand-600">•</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider bg-sand-900 text-sand-300 border border-sand-700 truncate max-w-[220px]">
                  Unit {currentChapter.unit_index}: {currentChapter.unit_name}
                </span>
              </>
            )}
            {currentChapter?.theory_source && (
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider border ${
                  currentChapter.theory_source === 'llm'
                    ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                    : 'bg-olive-500/15 text-olive-300 border-olive-500/30'
                }`}
                title={
                  currentChapter.theory_source === 'llm'
                    ? 'Theory enriched by the fine-tuned local Llama model'
                    : 'Theory built offline from the source text'
                }
              >
                {currentChapter.theory_source === 'llm' ? 'Local Llama' : 'Offline Grounded'}
              </span>
            )}
          </div>

          <h2 className="text-xl sm:text-2xl font-extrabold text-sand-50 tracking-tight">
            {currentChapter?.title || courseTitle}
          </h2>

          {/* Warm analogy pull-quote hook */}
          {hookAnalogy && viewMode === 'reader' && (
            <div className="mt-3 flex items-start gap-2.5 bg-amber-500/10 border border-amber-500/25 rounded-2xl px-4 py-2.5">
              <Lightbulb className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <p className="text-xs text-amber-100 leading-relaxed italic font-serif">{hookAnalogy}</p>
            </div>
          )}

          {/* Subsection outline pills */}
          {currentChapter?.subsections?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {currentChapter.subsections.map((sub, i) => {
                const pillLabel = sub.label || sub.sec_idx || i + 1;
                return (
                  <span
                    key={sub.section_id || i}
                    className="px-2 py-0.5 rounded-lg text-[10px] font-mono bg-sand-900 text-sand-400 border border-sand-800 hover:text-sand-200 transition"
                    title={sub.title || ''}
                  >
                    §{pillLabel}
                    {sub.title
                      ? ` · ${sub.title.length > 30 ? sub.title.slice(0, 28) + '…' : sub.title}`
                      : ''}
                  </span>
                );
              })}
            </div>
          )}
        </div>

        {/* RIGHT: view mode toggle + nav arrows + practice button */}
        <div className="flex items-center gap-2 self-start md:self-auto shrink-0 flex-wrap">
          {/* Prev / Next chapter arrows */}
          {chapters.length > 1 && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => hasPrev && handleChapterChange(currentChapterIndex - 1)}
                disabled={!hasPrev}
                className="p-2 rounded-xl bg-sand-900 border border-sand-800 text-sand-400 hover:text-sand-100 hover:border-sand-700 transition disabled:opacity-30 disabled:cursor-not-allowed"
                title="Previous chapter"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => hasNext && handleChapterChange(currentChapterIndex + 1)}
                disabled={!hasNext}
                className="p-2 rounded-xl bg-sand-900 border border-sand-800 text-sand-400 hover:text-sand-100 hover:border-sand-700 transition disabled:opacity-30 disabled:cursor-not-allowed"
                title="Next chapter"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* View mode toggle */}
          <div className="flex bg-sand-900/90 p-1 rounded-2xl border border-sand-800 shadow-inner">
            <button
              onClick={() => setViewMode('reader')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                viewMode === 'reader'
                  ? `${colors.bg} text-white shadow-md font-bold`
                  : 'text-sand-400 hover:text-sand-200'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>Reader</span>
            </button>
            <button
              onClick={() => setViewMode('matrix')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                viewMode === 'matrix'
                  ? `${colors.bg} text-white shadow-md font-bold`
                  : 'text-sand-400 hover:text-sand-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Matrix</span>
            </button>
            <button
              onClick={() => setViewMode('cards')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                viewMode === 'cards'
                  ? `${colors.bg} text-white shadow-md font-bold`
                  : 'text-sand-400 hover:text-sand-200'
              }`}
            >
              <Atom className="w-3.5 h-3.5" />
              <span>Deck ({displayedCards.length})</span>
            </button>
          </div>

          {onNavigateToPractice && (
            <button
              onClick={onNavigateToPractice}
              className="bg-gradient-to-r from-olive-600 to-amber-600 hover:from-olive-500 hover:to-amber-500 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-lg shadow-sand-300/25 transition flex items-center gap-1.5 active:scale-95"
            >
              <span>Practice Lab</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ======================================================== */}
      {/* VIEW MODE 1: FULL EDITORIAL THEORY READER (SPACIOUS)      */}
      {/* ======================================================== */}
      {viewMode === 'reader' && (
        <div className="space-y-6">
          {/* Executive Overview & Learning Objectives */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 glass-panel p-6 sm:p-8 rounded-3xl border border-sand-800 space-y-4">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-clay-400">
                <Sparkles className="w-4 h-4" />
                <span>Executive Theory Synthesis</span>
              </div>
              <p className="text-sm sm:text-base text-sand-200 leading-relaxed font-serif">
                {currentChapter?.summary || "Foundational theoretical overview and structured takeaways for this learning module."}
              </p>
            </div>

            {/* Learning Objectives Card */}
            <div className="glass-panel p-6 rounded-3xl border border-sand-800 space-y-3 bg-gradient-to-b from-sand-900/60 to-clay-950/20">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-olive-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>Core Learning Objectives</span>
              </div>
              <ul className="space-y-2.5">
                {objectives.map((obj, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-xs sm:text-sm text-sand-300 leading-relaxed">
                    <span className="w-4 h-4 rounded-full bg-olive-500/20 text-olive-400 font-mono text-[10px] flex items-center justify-center shrink-0 mt-0.5 font-bold">
                      {i + 1}
                    </span>
                    <span>{obj}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Section 1: Core Axioms & Governing Principles */}
          <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-sand-800 space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-ember-500/20 text-ember-400 rounded-2xl border border-ember-500/30">
                  <Atom className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-sand-50">Governing Principles & Definitions</h3>
                  <p className="text-xs text-sand-400">Invariant axioms and fundamental mechanics established by this module</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {principles.map((pr, idx) => (
                <div key={idx} className="p-5 rounded-2xl bg-sand-900/70 border border-sand-800 hover:border-ember-500/40 transition-all space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono uppercase bg-ember-500/20 text-ember-300 font-semibold">
                      {pr.tag || "Core Axiom"}
                    </span>
                    <button 
                      onClick={() => handleCopy(pr.content, `pr_${idx}`)}
                      className="text-sand-500 hover:text-sand-300 p-1 rounded transition"
                      title="Copy excerpt"
                    >
                      {copiedId === `pr_${idx}` ? <Check className="w-3.5 h-3.5 text-olive-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  <h4 className="text-sm font-bold text-sand-100">{pr.title}</h4>
                  <p className="text-xs sm:text-sm text-sand-300 leading-relaxed">{pr.content}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Section 2: Mathematical Formulations & Analytical Mechanics */}
          <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-sand-800 space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-clay-500/20 text-clay-400 rounded-2xl border border-clay-500/30">
                <Binary className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-sand-50">Mathematical Formulations & Derivations</h3>
                <p className="text-xs text-sand-400">Governing equations, variable relations, and analytical rules</p>
              </div>
            </div>

            <div className="space-y-4">
              {formulations.map((fm, idx) => (
                <div key={idx} className="p-6 rounded-2xl bg-sand-950 border border-clay-500/20 space-y-4 shadow-lg">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-sand-900">
                    <h4 className="text-sm font-bold text-clay-200">{fm.title}</h4>
                    <span className="text-[10px] font-mono text-sand-400 bg-sand-900 px-2.5 py-1 rounded-lg border border-sand-800">
                      Analytical Specification
                    </span>
                  </div>

                  {/* Formula Display Box with Copy Button */}
                  <div className="relative group">
                    <div className="p-4 rounded-xl bg-clay-950/30 border border-clay-500/30 text-clay-100 font-mono text-sm sm:text-base text-center overflow-x-auto shadow-inner">
                      {fm.formula}
                    </div>
                    <button
                      onClick={() => handleCopy(fm.formula, `fm_${idx}`)}
                      className="absolute right-2 top-2 p-1.5 rounded-lg bg-sand-900/80 border border-sand-700 text-sand-400 hover:text-sand-100 opacity-0 group-hover:opacity-100 transition"
                      title="Copy formula"
                    >
                      {copiedId === `fm_${idx}` ? <Check className="w-3.5 h-3.5 text-olive-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div className="p-3.5 rounded-xl bg-sand-900/50 border border-sand-800/80">
                      <span className="text-[10px] font-bold uppercase text-sand-400 block mb-1">Derivation Logic</span>
                      <p className="text-sand-300 text-xs sm:text-sm leading-relaxed">{fm.derivation}</p>
                    </div>
                    <div className="p-3.5 rounded-xl bg-sand-900/50 border border-sand-800/80">
                      <span className="text-[10px] font-bold uppercase text-sand-400 block mb-1">State Variables & Constants</span>
                      <p className="text-sand-300 text-xs sm:text-sm leading-relaxed">{fm.variables}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Section 3: Dual Grid - Mental Models & Cognitive Misconceptions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Mental Model & Analogies */}
            <div className="glass-panel p-6 rounded-3xl border border-sand-800 space-y-4 bg-gradient-to-br from-sand-900/80 via-sand-950 to-amber-950/10">
              <div className="flex items-center gap-2.5 text-xs font-bold uppercase tracking-wider text-amber-500">
                <Lightbulb className="w-4 h-4" />
                <span>Mental Models & Analogies</span>
              </div>
              {mentalModels.map((mm, idx) => (
                <div key={idx} className="space-y-2.5">
                  <h4 className="text-sm font-bold text-sand-50">{mm.concept}</h4>
                  <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs sm:text-sm text-amber-100 leading-relaxed font-serif">
                    {mm.analogy}
                  </div>
                  <div className="text-xs text-sand-300 flex items-start gap-2">
                    <strong className="text-amber-400 shrink-0">Key Intuition:</strong>
                    <span>{mm.takeaway}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Cognitive Traps & Misconceptions */}
            <div className="glass-panel p-6 rounded-3xl border border-sand-800 space-y-4 bg-gradient-to-br from-sand-900/80 via-sand-950 to-clay-950/10">
              <div className="flex items-center gap-2.5 text-xs font-bold uppercase tracking-wider text-clay-400">
                <AlertTriangle className="w-4 h-4" />
                <span>Diagnostic Pitfalls & Misconceptions</span>
              </div>
              {misconceptions.map((mc, idx) => (
                <div key={idx} className="space-y-2.5">
                  <div className="text-xs text-clay-300 font-semibold flex items-start gap-2">
                    <span className="text-clay-400 font-bold shrink-0">⚠ Trap:</span>
                    <span>{mc.trap}</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-clay-500/10 border border-clay-500/20 text-xs sm:text-sm text-sand-200 leading-relaxed">
                    <strong className="text-olive-400 block mb-1">Correct Conceptual Approach:</strong>
                    {mc.correction}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Section 3b: Section-by-Section Study Map (from the book's own TOC) */}
          {currentChapter?.section_texts?.length > 0 && (
            <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-sand-800 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-olive-500/20 text-olive-400 rounded-2xl border border-olive-500/30">
                    <Layers className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-sand-50">Section-by-Section Study Map</h3>
                    <p className="text-xs text-sand-400">
                      {currentChapter.section_texts.length} sections mapped from the textbook — tap to read
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setExpandAllSections(!expandAllSections)}
                  className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-sand-900 border border-sand-800 text-sand-300 hover:text-sand-100 hover:border-sand-700 transition flex items-center gap-1.5"
                >
                  {expandAllSections ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                  <span>{expandAllSections ? 'Collapse All' : 'Expand All'}</span>
                </button>
              </div>

              <div className="space-y-2.5">
                {currentChapter.section_texts.map((sec, idx) => {
                  const key = sec.section_id || `${idx}`;
                  const isOpen = expandAllSections || openSection === key;
                  const wordCount = Math.round((sec.content?.length || 0) / 5);
                  const estMinutes = Math.max(1, Math.round(wordCount / 180));

                  return (
                    <div key={key} className="rounded-2xl bg-sand-900/70 border border-sand-800 overflow-hidden transition-all">
                      <button
                        onClick={() => {
                          if (expandAllSections) setExpandAllSections(false);
                          setOpenSection(openSection === key ? null : key);
                        }}
                        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-sand-800/40 transition"
                      >
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-clay-500/20 text-clay-300 border border-clay-500/30 shrink-0 font-bold">
                          {sec.label}
                        </span>
                        <span className="flex-1 text-xs sm:text-sm font-semibold text-sand-200 truncate">
                          {sec.title}
                        </span>
                        <span className="text-[10px] font-mono text-sand-400 shrink-0 bg-sand-950 px-2 py-0.5 rounded border border-sand-800">
                          ~{wordCount}w · {estMinutes}m read
                        </span>
                        {isOpen ? <ChevronDown className="w-4 h-4 text-sand-400 shrink-0" /> : <ChevronRight className="w-4 h-4 text-sand-400 shrink-0" />}
                      </button>
                      {isOpen && (
                        <div className="px-5 pb-5 pt-2 max-h-[460px] overflow-y-auto custom-scrollbar animate-fadeIn border-t border-sand-800 bg-sand-950/40">
                          {renderSourceAsProse(sec.content)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Section 3c: Key Terms & Glossary (source-extracted) */}
          {keyTerms.length > 0 && (
            <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-sand-800 space-y-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-olive-500/20 text-olive-400 rounded-2xl border border-olive-500/30">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-sand-50">Key Terms & Glossary</h3>
                  <p className="text-xs text-sand-400">Definitions extracted directly from the chapter text</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {keyTerms.map((kt, idx) => (
                  <div key={idx} className="p-4 rounded-2xl bg-sand-900/70 border border-sand-800 space-y-1.5 hover:border-sand-700 transition">
                    <h4 className="text-sm font-bold text-sand-100">{kt.term}</h4>
                    <p className="text-xs text-sand-300 leading-relaxed">{kt.definition}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section 3d: Worked Examples */}
          {workedExamples.length > 0 && (
            <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-sand-800 space-y-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-clay-500/20 text-clay-400 rounded-2xl border border-clay-500/30">
                  <HelpCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-sand-50">Worked Examples from the Source</h3>
                  <p className="text-xs text-sand-400">Solved-problem walkthroughs taken directly from the chapter</p>
                </div>
              </div>

              <div className="space-y-3">
                {workedExamples.map((we, idx) => (
                  <div key={idx} className="p-5 rounded-2xl bg-sand-950 border border-sand-800 space-y-2">
                    <h4 className="text-xs font-bold text-ember-300 uppercase tracking-wider">
                      {we.title || `Example ${idx + 1}`}
                    </h4>
                    <p className="text-xs sm:text-sm text-sand-300 leading-relaxed whitespace-pre-line">
                      {we.content}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section 4: Expandable Full Original Source Material */}
          {currentChapter?.full_text && (
            <div className="glass-panel p-6 rounded-3xl border border-sand-800 space-y-3">
              <button
                onClick={() => setShowFullSource(!showFullSource)}
                className="w-full flex items-center justify-between text-left text-xs font-bold text-sand-300 hover:text-sand-50 transition"
              >
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-clay-400" />
                  <span>Inspect Complete Ingested Chapter Source Text (~{Math.round(currentChapter.full_text.length / 5)} words)</span>
                </div>
                {showFullSource ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </button>

              {showFullSource && (
                <div className="p-5 rounded-2xl bg-sand-950 border border-sand-900 max-h-[520px] overflow-y-auto custom-scrollbar animate-fadeIn">
                  {renderSourceAsProse(currentChapter.full_text)}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ======================================================== */}
      {/* VIEW MODE 2: CONCEPT MATRIX (MODULAR INTERACTIVE TILES)   */}
      {/* ======================================================== */}
      {viewMode === 'matrix' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 animate-fadeIn">
          {displayedCards.map((card, idx) => {
            const isExpanded = expandedSection === idx;
            return (
              <div
                key={card.id || idx}
                onClick={() => setExpandedSection(isExpanded ? null : idx)}
                className={`glass-panel p-6 rounded-3xl border transition-all duration-300 cursor-pointer flex flex-col justify-between ${
                  isExpanded
                    ? 'border-clay-500 bg-sand-900/90 shadow-2xl shadow-sand-300/25 ring-1 ring-clay-500/50'
                    : 'border-sand-800 hover:border-sand-700 bg-sand-900/50 hover:bg-sand-900/80 hover:-translate-y-0.5'
                }`}
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-clay-500/20 text-clay-300 border border-clay-500/30">
                      Concept {idx + 1}
                    </span>
                    <span className="text-[10px] font-mono text-sand-500">
                      {isExpanded ? 'Click to collapse' : 'Click to expand'}
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-sand-50 transition">
                    {card.topic || `Concept ${idx + 1}`}
                  </h3>

                  <p className="text-xs font-semibold text-clay-200 leading-snug">
                    {card.question}
                  </p>

                  <div className={`text-xs sm:text-sm text-sand-300 leading-relaxed pt-2 border-t border-sand-800/80 whitespace-pre-line ${
                    isExpanded ? 'block' : 'line-clamp-4'
                  }`}>
                    {card.answer}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-sand-800/50 flex items-center justify-between text-[11px] text-clay-400 font-bold">
                  <span>{isExpanded ? 'Detailed Breakdown Active' : 'Read Deep Breakdown'}</span>
                  <ChevronRight className={`w-3.5 h-3.5 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ======================================================== */}
      {/* VIEW MODE 3: WIDE ACTIVE STUDY DECK (SPACIOUS 3D FLIP)    */}
      {/* ======================================================== */}
      {viewMode === 'cards' && (
        <div className="glass-panel p-6 sm:p-10 rounded-3xl border border-sand-800 shadow-2xl space-y-6 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-sand-800 pb-4">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-clay-400" />
              <span className="text-xs font-bold text-sand-50">
                Focus Study Card {displayedCards.length > 0 ? Math.min(cardIndex + 1, displayedCards.length) : 0} of {displayedCards.length}
              </span>
            </div>
            <div className="flex items-center gap-3 text-[11px] font-mono text-sand-400">
              <span className="hidden sm:inline text-sand-500">Shortcut: Space/Click to flip • ←/→ to navigate</span>
              <span className="px-2 py-0.5 rounded bg-sand-900 border border-sand-800 text-clay-300">
                {isFlipped ? 'Answer View' : 'Question View'}
              </span>
            </div>
          </div>

          {displayedCards.length > 0 ? (
            <div className="flex flex-col items-center justify-center py-4">
              <div 
                onClick={() => setIsFlipped(!isFlipped)} 
                className="flip-card w-full max-w-3xl h-[400px] sm:h-[440px] cursor-pointer group"
              >
                <div className={`flip-card-inner ${isFlipped ? 'flipped' : ''}`}>
                  
                  {/* FRONT SIDE (PROMPT) */}
                  <div className="flip-card-front bg-gradient-to-br from-sand-900 via-sand-950 to-clay-950/40 border border-clay-900/40 hover:border-clay-500/60 p-8 sm:p-10 flex flex-col justify-between items-center text-center shadow-2xl rounded-3xl relative overflow-hidden transition-all duration-300">
                    <div className="flex items-center justify-between w-full">
                      <span className="px-3 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider bg-clay-500/20 text-clay-300 font-bold border border-clay-500/30">
                        {displayedCards[cardIndex]?.topic || 'Core Theory'}
                      </span>
                      <span className="text-[10px] font-mono text-sand-500">Front (Prompt)</span>
                    </div>

                    <div className="my-auto py-6 max-w-xl space-y-3">
                      <div className="w-12 h-12 rounded-2xl bg-clay-500/10 text-clay-400 flex items-center justify-center mx-auto border border-clay-500/20 shadow-inner">
                        <HelpCircle className="w-6 h-6" />
                      </div>
                      <h3 className="text-lg sm:text-xl font-bold text-sand-50 leading-relaxed">
                        {displayedCards[cardIndex]?.question}
                      </h3>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-clay-400 font-semibold group-hover:translate-y-[-2px] transition">
                      <span>Click or press Spacebar to flip</span>
                      <ChevronRight className="w-4 h-4" />
                    </div>
                  </div>

                  {/* BACK SIDE (SOLUTION & BULLETS) */}
                  <div className="flip-card-back bg-gradient-to-br from-sand-900 via-clay-950/50 to-sand-950 border border-clay-500/60 p-8 sm:p-10 flex flex-col justify-between text-left shadow-2xl rounded-3xl overflow-y-auto custom-scrollbar">
                    <div className="flex items-center justify-between w-full pb-3 border-b border-clay-500/30">
                      <span className="px-3 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider bg-olive-500/20 text-olive-300 font-bold border border-olive-500/30">
                        {displayedCards[cardIndex]?.topic || 'Theory Breakdown'}
                      </span>
                      <span className="text-[10px] font-mono text-clay-300">Back (Synthesis)</span>
                    </div>

                    <div className="my-4 text-xs sm:text-sm text-sand-200 leading-relaxed whitespace-pre-line space-y-2 overflow-y-auto custom-scrollbar max-h-[240px]">
                      {displayedCards[cardIndex]?.answer}
                    </div>

                    <div className="flex items-center justify-between text-xs text-sand-400 pt-3 border-t border-clay-500/20">
                      <span>Card {cardIndex + 1} of {displayedCards.length}</span>
                      <span className="text-clay-400 font-semibold">Click to flip back</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* CARD CONTROLS */}
              <div className="flex items-center justify-center gap-4 mt-8">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setCardIndex(prev => Math.max(0, prev - 1));
                    setIsFlipped(false);
                  }}
                  disabled={cardIndex === 0}
                  className="p-3 rounded-2xl bg-sand-900 border border-sand-800 text-sand-300 hover:text-sand-50 hover:bg-sand-800 transition disabled:opacity-40 disabled:cursor-not-allowed shadow-md"
                  title="Previous card"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>

                <div className="flex gap-1.5 items-center">
                  {displayedCards.map((_, i) => (
                    <button
                      key={i}
                      onClick={(e) => {
                        e.stopPropagation();
                        setCardIndex(i);
                        setIsFlipped(false);
                      }}
                      className={`h-2 rounded-full transition-all ${
                        cardIndex === i ? 'w-8 bg-clay-500 shadow-md shadow-sand-300/25' : 'w-2 bg-sand-800 hover:bg-sand-700'
                      }`}
                    />
                  ))}
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setCardIndex(prev => Math.min(displayedCards.length - 1, prev + 1));
                    setIsFlipped(false);
                  }}
                  disabled={cardIndex === displayedCards.length - 1}
                  className="p-3 rounded-2xl bg-sand-900 border border-sand-800 text-sand-300 hover:text-sand-50 hover:bg-sand-800 transition disabled:opacity-40 disabled:cursor-not-allowed shadow-md"
                  title="Next card"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-sand-500 text-xs font-mono">
              No flashcards available for this chapter.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
