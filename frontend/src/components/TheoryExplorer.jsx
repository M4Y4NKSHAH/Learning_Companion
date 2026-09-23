import React, { useState } from 'react';
import { 
  BookOpen, 
  Sparkles, 
  Layers, 
  Cpu, 
  ArrowRight, 
  ChevronRight, 
  ChevronDown,
  ChevronLeft,
  Lightbulb, 
  AlertTriangle, 
  Compass, 
  CheckCircle2, 
  FileText, 
  Maximize2,
  Atom,
  Binary,
  GraduationCap,
  HelpCircle,
  Copy,
  Check
} from 'lucide-react';
import ChapterNav from './ChapterNav';

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

  const currentChapter = (activeChapterIndex !== null && chapters[activeChapterIndex]) 
    ? chapters[activeChapterIndex] 
    : (chapters.length > 0 ? chapters[0] : null);

  const displayedCards = (currentChapter && currentChapter.cards && currentChapter.cards.length > 0)
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
  const applications = deepTheory.applications || [
    {
      domain: "Real-World Systems & Engineering Context",
      description: "Directly applied in designing analytical frameworks, predictive models, and diagnostic pipelines."
    }
  ];
  const misconceptions = deepTheory.misconceptions || [
    {
      trap: "Superficial Formula Application Without Verifying Operational Domain",
      correction: "Always isolate state variables and confirm boundary assumptions before executing derivations or problem sets."
    }
  ];

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-fadeIn">
      {/* CHAPTER SELECTION PILL BAR */}
      {chapters.length > 1 && (
        <ChapterNav
          chapters={chapters}
          activeChapterIndex={activeChapterIndex}
          onSelectChapter={(idx) => {
            onSelectChapter(idx);
            setCardIndex(0);
            setIsFlipped(false);
            setExpandedSection(null);
          }}
          activeColor={activeColor}
        />
      )}

      {/* TOP HEADER CONTROLS */}
      <div className="glass-panel p-6 rounded-3xl border border-sand-800 shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider bg-clay-500/20 text-clay-300 border border-clay-500/30">
              Interactive Theory Explorer
            </span>
            <span className="text-sand-600">•</span>
            <span className="text-xs font-mono text-sand-400">
              {currentChapter ? `Chapter ${currentChapter.chapter_index || 1} of ${chapters.length || 1}` : courseTitle}
            </span>
          </div>
          <h2 className="text-xl font-extrabold text-sand-50 tracking-tight">
            {currentChapter?.title || courseTitle}
          </h2>
          <p className="text-xs text-sand-400 mt-1 max-w-2xl">
            {currentChapter?.summary ? currentChapter.summary.slice(0, 160) + '...' : 'Explore detailed theoretical principles, mathematical formulations, and mental models.'}
          </p>
        </div>

        {/* VIEW MODE TOGGLE BUTTONS */}
        <div className="flex items-center gap-2 self-start md:self-auto">
          <div className="flex bg-sand-900/80 p-1 rounded-2xl border border-sand-800">
            <button
              onClick={() => setViewMode('reader')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                viewMode === 'reader'
                  ? 'bg-clay-600 text-white shadow-lg shadow-sand-300/25'
                  : 'text-sand-400 hover:text-sand-200'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>Full Reader</span>
            </button>
            <button
              onClick={() => setViewMode('matrix')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                viewMode === 'matrix'
                  ? 'bg-clay-600 text-white shadow-lg shadow-sand-300/25'
                  : 'text-sand-400 hover:text-sand-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Concept Matrix</span>
            </button>
            <button
              onClick={() => setViewMode('cards')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                viewMode === 'cards'
                  ? 'bg-clay-600 text-white shadow-lg shadow-sand-300/25'
                  : 'text-sand-400 hover:text-sand-200'
              }`}
            >
              <Atom className="w-3.5 h-3.5" />
              <span>Active Deck ({displayedCards.length})</span>
            </button>
          </div>

          {onNavigateToPractice && (
            <button
              onClick={onNavigateToPractice}
              className="bg-gradient-to-r from-olive-600 to-amber-600 hover:from-olive-500 hover:to-amber-500 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-lg shadow-sand-300/25 transition flex items-center gap-1.5"
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
                {(currentChapter?.objectives || [
                  "Master fundamental definitions and mechanics",
                  "Apply analytical formulations to problem solving",
                  "Identify key boundary conditions and diagnostic traps"
                ]).map((obj, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-xs text-sand-300 leading-normal">
                    <span className="w-4 h-4 rounded-full bg-olive-500/20 text-olive-400 font-mono text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5 font-bold">
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
                  <p className="text-xs text-sand-300 leading-relaxed font-sans">{pr.content}</p>
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
                <div key={idx} className="p-6 rounded-2xl bg-sand-950 border border-clay-500/20 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-sand-900">
                    <h4 className="text-sm font-bold text-clay-200">{fm.title}</h4>
                    <span className="text-[10px] font-mono text-sand-400 bg-sand-900 px-2.5 py-1 rounded-lg border border-sand-800">
                      Analytical Specification
                    </span>
                  </div>

                  {/* Formula Display Box */}
                  <div className="p-4 rounded-xl bg-clay-950/20 border border-clay-500/30 text-clay-100 font-mono text-sm sm:text-base text-center overflow-x-auto shadow-inner">
                    {fm.formula}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div className="p-3 rounded-xl bg-sand-900/50 border border-sand-800/80">
                      <span className="text-[10px] font-bold uppercase text-sand-400 block mb-1">Derivation Logic</span>
                      <p className="text-sand-300">{fm.derivation}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-sand-900/50 border border-sand-800/80">
                      <span className="text-[10px] font-bold uppercase text-sand-400 block mb-1">State Variables & Constants</span>
                      <p className="text-sand-300">{fm.variables}</p>
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
              <div className="flex items-center gap-2.5 text-xs font-bold uppercase tracking-wider text-amber-800">
                <Lightbulb className="w-4 h-4" />
                <span>Mental Models & Analogies</span>
              </div>
              {mentalModels.map((mm, idx) => (
                <div key={idx} className="space-y-2.5">
                  <h4 className="text-sm font-bold text-sand-50">{mm.concept}</h4>
                  <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 leading-relaxed font-serif">
                    "{mm.analogy}"
                  </div>
                  <div className="text-xs text-sand-300 flex items-center gap-2">
                    <strong className="text-amber-800">Key Intuition:</strong>
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
                    <span className="text-clay-400 font-bold">⚠️ Trap:</span>
                    <span>{mc.trap}</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-clay-500/10 border border-clay-500/20 text-xs text-sand-200 leading-relaxed">
                    <strong className="text-olive-400 block mb-1">Correct Conceptual Approach:</strong>
                    {mc.correction}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Section 4: Expandable Full Original Source Material */}
          {currentChapter?.full_text && (
            <div className="glass-panel p-6 rounded-3xl border border-sand-800 space-y-3">
              <button
                onClick={() => setShowFullSource(!showFullSource)}
                className="w-full flex items-center justify-between text-left text-xs font-bold text-sand-300 hover:text-sand-50 transition"
              >
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-clay-400" />
                  <span>Inspect Complete Ingested Chapter Source Text ({Math.round(currentChapter.full_text.length / 5)} words)</span>
                </div>
                {showFullSource ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </button>

              {showFullSource && (
                <div className="p-5 rounded-2xl bg-sand-950 border border-sand-900 text-xs font-mono text-sand-300 max-h-[400px] overflow-y-auto custom-scrollbar leading-relaxed whitespace-pre-wrap animate-fadeIn">
                  {currentChapter.full_text}
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
                    : 'border-sand-800 hover:border-sand-700 bg-sand-900/50 hover:bg-sand-900/80'
                }`}
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-clay-500/20 text-clay-300 border border-clay-500/30">
                      Module Concept {idx + 1}
                    </span>
                    <span className="text-[10px] font-mono text-sand-500">
                      {isExpanded ? 'Click to collapse' : 'Click to expand'}
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-sand-50 group-hover:text-clay-300 transition">
                    {card.topic || `Concept ${idx + 1}`}
                  </h3>

                  <p className="text-xs font-semibold text-clay-200 leading-snug">
                    {card.question}
                  </p>

                  <div className={`text-xs text-sand-300 leading-relaxed font-sans pt-2 border-t border-sand-800/80 whitespace-pre-line ${
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
            <span className="text-[11px] font-mono text-sand-400">Click card or spacebar to flip</span>
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
                      <span className="text-[10px] font-mono text-sand-500">Front (Inquiry)</span>
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
                      <span>Click to reveal comprehensive answer</span>
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

                    <div className="my-4 text-xs sm:text-sm text-sand-200 leading-relaxed font-sans whitespace-pre-line space-y-2 overflow-y-auto custom-scrollbar max-h-[220px]">
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
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>

                <div className="flex gap-1.5">
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
