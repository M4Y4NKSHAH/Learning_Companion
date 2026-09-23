import React, { useState, useEffect, useRef } from 'react';
import { 
  Upload, 
  FileText, 
  Sparkles, 
  Trash2, 
  BookOpen, 
  Layers, 
  BrainCircuit, 
  CheckCircle2, 
  AlertCircle, 
  Cpu, 
  FileCheck, 
  Loader2, 
  ChevronRight, 
  ArrowRight,
  Plus,
  Compass,
  GraduationCap,
  FileCode,
  Check,
  Clock
} from 'lucide-react';

const SUBJECT_OPTIONS = ['Physics', 'Biology', 'Mathematics', 'Computer Science', 'General Science', 'Engineering', 'Economics'];
const TIER_OPTIONS = ['Class 10', 'Class 11-12', 'Undergraduate', 'Graduate', 'Professional'];

export default function CourseStudioView({
  courses = [],
  activeCourseId = null,
  onSelectCourse,
  onDeleteCourse,
  onCourseCreated,
  onNavigateToStudy,
  onNavigateToPractice,
  activeColor = 'clay'
}) {
  const [activeTab, setActiveTab] = useState('studio'); // 'studio' | 'create'
  const [createMode, setCreateMode] = useState('upload'); // 'upload' | 'text'
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('Physics');
  const [tier, setTier] = useState('Undergraduate');
  const [rawText, setRawText] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  
  // Pipeline processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState(0);
  const [errorMsg, setErrorMsg] = useState(null);

  const fileInputRef = useRef(null);

  const activeCourse = courses.find(c => c.course_id === activeCourseId) || courses[0] || null;

  const handleFileDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
      if (!title) {
        setTitle(file.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      if (!title) {
        setTitle(file.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

  const handleSubmitIngestion = async (e) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!title.trim()) {
      setErrorMsg('Please enter a descriptive course or topic title.');
      return;
    }

    if (createMode === 'upload' && !selectedFile) {
      setErrorMsg('Please select a PDF, TXT, or Markdown document to upload.');
      return;
    }

    if (createMode === 'text' && rawText.trim().length < 50) {
      setErrorMsg('Please paste at least 50 characters of lecture notes or study material.');
      return;
    }

    setIsProcessing(true);
    setProcessingStep(1);

    try {
      const timer1 = setTimeout(() => setProcessingStep(2), 900);
      const timer2 = setTimeout(() => setProcessingStep(3), 2400);
      const timer3 = setTimeout(() => setProcessingStep(4), 4200);

      let response;
      if (createMode === 'upload') {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('title', title);
        formData.append('subject', subject);
        formData.append('academic_tier', tier);

        response = await fetch('http://127.0.0.1:8000/api/material/upload', {
          method: 'POST',
          body: formData,
        });
      } else {
        response = await fetch('http://127.0.0.1:8000/api/material/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title,
            subject,
            academic_tier: tier,
            raw_text: rawText,
            generate_questions_immediately: true,
          }),
        });
      }

      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);

      if (!response.ok) {
        let errMessage = `Upload error (${response.status})`;
        try {
          const err = await response.json();
          errMessage = err.detail || err.message || errMessage;
        } catch {
          errMessage = `Server returned error ${response.status}`;
        }
        throw new Error(errMessage);
      }

      const data = await response.json();
      setProcessingStep(5);

      setTimeout(() => {
        setIsProcessing(false);
        setProcessingStep(0);
        setTitle('');
        setRawText('');
        setSelectedFile(null);
        setActiveTab('studio');
        if (onCourseCreated) {
          onCourseCreated(data.course);
        }
      }, 1000);

    } catch (err) {
      console.error(err);
      let message = err.message || 'An error occurred during material processing.';
      if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
        message = 'Could not connect to backend server. Please ensure FastAPI backend is running on port 8000.';
      }
      setErrorMsg(message);
      setIsProcessing(false);
      setProcessingStep(0);
    }
  };

  const [elapsedSec, setElapsedSec] = useState(0);

  React.useEffect(() => {
    let timer = null;
    if (isProcessing) {
      setElapsedSec(0);
      timer = setInterval(() => {
        setElapsedSec((prev) => prev + 1);
      }, 1000);
    } else {
      clearInterval(timer);
    }
    return () => clearInterval(timer);
  }, [isProcessing]);

  const steps = [
    { label: 'Parsing Document & Normalizing Sections', icon: FileText, desc: 'Extracting pages, stripping artifacts & noise' },
    { label: 'Decomposing Outline into Logical Chapters', icon: Layers, desc: 'Detecting sections & isolating core theory' },
    { label: 'Synthesizing Theory Summaries & Flashcards', icon: BookOpen, desc: 'Generating structured flashcards & takeaways' },
    { label: 'Vectorizing Embeddings into ChromaDB', icon: Cpu, desc: 'Indexing semantic knowledge chunks' },
    { label: 'Generating Practice Quizzes & Exam Items', icon: BrainCircuit, desc: 'Synthesizing evaluation question bank' },
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Top Banner & Mode Toggle */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 glass-panel p-6 rounded-2xl border border-sand-800">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="p-2 bg-gradient-to-tr from-clay-600 to-ember-600 rounded-xl text-white shadow-lg shadow-sand-300/25">
              <Layers className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-bold text-sand-50 tracking-tight">Course Studio & Material Ingestion</h2>
          </div>
          <p className="text-xs text-sand-400 max-w-xl">
            Ingest custom textbooks, PDF research papers, or syllabus notes. Our AI decomposes materials into chapters, high-retention flashcard decks, and testing banks.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('studio')}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'studio'
                ? 'bg-sand-200 text-sand-900 shadow-md font-bold'
                : 'bg-sand-900/60 border border-sand-800 text-sand-400 hover:text-sand-50'
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            Course Library ({courses.length})
          </button>
          <button
            onClick={() => setActiveTab('create')}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 shadow-lg ${
              activeTab === 'create'
                ? 'bg-gradient-to-r from-clay-600 to-ember-600 text-white shadow-sand-300/25'
                : 'bg-clay-950/40 border border-clay-500/30 text-clay-300 hover:bg-clay-900/40'
            }`}
          >
            <Plus className="w-3.5 h-3.5" />
            Ingest New Material
          </button>
        </div>
      </div>

      {/* VIEW 1: CREATE / INGEST NEW MATERIAL */}
      {activeTab === 'create' && (
        <div className="glass-panel p-6 md:p-8 rounded-2xl border border-clay-500/20 shadow-2xl">
          {isProcessing ? (
            <div className="py-8 flex flex-col items-center justify-center text-center">
              <div className="relative mb-5">
                <div className="w-20 h-20 rounded-full border-4 border-clay-500/20 border-t-clay-500 animate-spin flex items-center justify-center">
                  <BrainCircuit className="w-8 h-8 text-clay-400 animate-pulse" />
                </div>
              </div>
              <h3 className="text-lg font-bold text-sand-50 mb-1">Synthesizing Course Structure & Question Bank</h3>
              <p className="text-xs text-sand-400 mb-4 max-w-md">
                Decomposing sections, generating structured bullet flashcards, and generating misconception-mapped exam items.
              </p>

              {/* Live Elapsed Badge */}
              <div className="flex items-center gap-2 mb-6 px-3.5 py-1.5 rounded-full bg-sand-950 border border-sand-800 text-[11px] font-mono text-sand-300">
                <Clock className="w-3.5 h-3.5 text-clay-400 animate-pulse" />
                <span>Elapsed: <strong className="text-sand-50">{elapsedSec}s</strong></span>
                <span className="text-sand-600">•</span>
                <span className="text-clay-300">
                  {processingStep === 1 && "Parsing PDF stream..."}
                  {processingStep === 2 && "Analyzing outline..."}
                  {processingStep === 3 && "Synthesizing AI cards..."}
                  {processingStep === 4 && "Vectorizing embeddings & tests..."}
                  {processingStep >= 5 && "Completed!"}
                </span>
              </div>

              <div className="w-full max-w-md space-y-2.5 text-left mb-4">
                {steps.map((step, idx) => {
                  const stepNum = idx + 1;
                  const isDone = processingStep > stepNum;
                  const isCurrent = processingStep === stepNum;
                  const StepIcon = step.icon;

                  return (
                    <div
                      key={idx}
                      className={`flex items-center justify-between p-3 rounded-xl border transition-all duration-300 ${
                        isDone
                          ? 'bg-olive-500/10 border-olive-500/30 text-olive-300'
                          : isCurrent
                            ? 'bg-clay-500/10 border-clay-500/40 text-clay-200 shadow-lg shadow-sand-300/25'
                            : 'bg-sand-900/40 border-sand-800 text-sand-500'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`p-1.5 rounded-lg ${
                          isDone ? 'bg-olive-500/20 text-olive-400' : isCurrent ? 'bg-clay-500/20 text-clay-400' : 'bg-sand-800 text-sand-600'
                        }`}>
                          {isDone ? (
                            <CheckCircle2 className="w-4 h-4 text-olive-400" />
                          ) : isCurrent ? (
                            <Loader2 className="w-4 h-4 animate-spin text-clay-400" />
                          ) : (
                            <StepIcon className="w-4 h-4" />
                          )}
                        </div>
                        <div>
                          <div className="text-xs font-semibold">{step.label}</div>
                          <div className="text-[10px] text-sand-400">{step.desc}</div>
                        </div>
                      </div>

                      {isDone && <span className="text-[10px] font-mono text-olive-400 font-bold">Done</span>}
                      {isCurrent && <span className="text-[10px] font-mono text-clay-400 font-bold animate-pulse">In Progress...</span>}
                    </div>
                  );
                })}
              </div>

              {elapsedSec > 10 && (
                <p className="text-[11px] text-sand-500 font-mono italic max-w-md">
                  💡 Processing extensive multi-page textbook/paper. Generating high-retention flashcards and embedding vector database...
                </p>
              )}
            </div>
          ) : (
            <form onSubmit={handleSubmitIngestion} className="space-y-6 max-w-3xl mx-auto">
              <div>
                <h3 className="text-base font-bold text-sand-50 mb-1">Ingest Material Into Dynamic Curriculum</h3>
                <p className="text-xs text-sand-400">
                  Upload a PDF (e.g. Research paper, chapter PDF, textbook excerpt) or paste raw markdown notes.
                </p>
              </div>

              {errorMsg && (
                <div className="flex items-center gap-2.5 p-3.5 bg-clay-500/10 border border-clay-500/30 rounded-xl text-clay-300 text-xs">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* Mode Tabs */}
              <div className="flex bg-sand-900/80 p-1.5 rounded-xl border border-sand-800">
                <button
                  type="button"
                  onClick={() => setCreateMode('upload')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-xs font-semibold rounded-lg transition ${
                    createMode === 'upload' ? 'bg-clay-600 text-white shadow-md' : 'text-sand-400 hover:text-sand-50'
                  }`}
                >
                  <Upload className="w-4 h-4" />
                  Upload Document (PDF / TXT / MD)
                </button>
                <button
                  type="button"
                  onClick={() => setCreateMode('text')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-xs font-semibold rounded-lg transition ${
                    createMode === 'text' ? 'bg-clay-600 text-white shadow-md' : 'text-sand-400 hover:text-sand-50'
                  }`}
                >
                  <FileText className="w-4 h-4" />
                  Paste Notes / Syllabus Text
                </button>
              </div>

              {/* Title & Metadata */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-3">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-sand-300 mb-1.5">
                    Course / Topic Title *
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Research Paper - GR.05, Advanced Organic Synthesis, Classical Mechanics"
                    className="w-full bg-sand-900/90 border border-sand-700 rounded-xl px-4 py-2.5 text-xs text-sand-50 placeholder-sand-500 focus:outline-none focus:border-clay-500 focus:ring-1 focus:ring-clay-500"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-sand-300 mb-1.5">
                    Subject Field
                  </label>
                  <select
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="w-full bg-sand-900/90 border border-sand-700 rounded-xl px-3 py-2.5 text-xs text-sand-50 focus:outline-none focus:border-clay-500"
                  >
                    {SUBJECT_OPTIONS.map((s) => (
                      <option key={s} value={s} className="bg-sand-900">{s}</option>
                    ))}
                  </select>
                </div>

                <div className="md:col-span-2">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-sand-300 mb-1.5">
                    Target Academic Level
                  </label>
                  <select
                    value={tier}
                    onChange={(e) => setTier(e.target.value)}
                    className="w-full bg-sand-900/90 border border-sand-700 rounded-xl px-3 py-2.5 text-xs text-sand-50 focus:outline-none focus:border-clay-500"
                  >
                    {TIER_OPTIONS.map((t) => (
                      <option key={t} value={t} className="bg-sand-900">{t}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Source Input */}
              {createMode === 'upload' ? (
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-sand-300 mb-2">
                    Source Document (PDF, TXT, MD) *
                  </label>
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleFileDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition flex flex-col items-center justify-center ${
                      selectedFile
                        ? 'border-olive-500/60 bg-olive-500/5 text-olive-300'
                        : 'border-sand-700 hover:border-clay-500/60 bg-sand-900/40 hover:bg-clay-950/10'
                    }`}
                  >
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileChange}
                      accept=".pdf,.txt,.md"
                      className="hidden"
                    />
                    {selectedFile ? (
                      <div className="flex items-center gap-4">
                        <div className="p-3 bg-olive-500/20 rounded-xl text-olive-400">
                          <FileCheck className="w-8 h-8" />
                        </div>
                        <div className="text-left">
                          <div className="text-sm font-semibold text-sand-50">{selectedFile.name}</div>
                          <div className="text-xs text-olive-400">
                            {(selectedFile.size / 1024).toFixed(1)} KB • Ready for automated decomposition
                          </div>
                        </div>
                      </div>
                    ) : (
                      <>
                        <Upload className="w-10 h-10 text-clay-400 mb-3" />
                        <div className="text-sm font-semibold text-sand-200">Drag & drop your document here, or click to browse</div>
                        <div className="text-xs text-sand-500 mt-1">Supports PDF research papers, textbooks (.pdf), text (.txt), and markdown (.md)</div>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-sand-300 mb-2">
                    Paste Lecture Notes, Syllabus, or Book Sections *
                  </label>
                  <textarea
                    value={rawText}
                    onChange={(e) => setRawText(e.target.value)}
                    rows={8}
                    placeholder="Paste textbook text, notes, or paper sections here... (Headings like # Chapter 1 or 1. Introduction are automatically organized)"
                    className="w-full bg-sand-900/90 border border-sand-700 rounded-xl p-4 text-xs text-sand-50 placeholder-sand-500 focus:outline-none focus:border-clay-500 focus:ring-1 focus:ring-clay-500 font-mono leading-relaxed custom-scrollbar"
                  />
                  <div className="text-right text-[11px] text-sand-500 mt-1">{rawText.length} characters</div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setActiveTab('studio')}
                  className="px-5 py-2.5 rounded-xl text-xs font-semibold text-sand-400 hover:text-sand-50 hover:bg-sand-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-clay-600 via-amber-600 to-ember-600 hover:from-clay-500 hover:to-ember-500 shadow-xl shadow-sand-300/25 transition active:scale-95"
                >
                  <Sparkles className="w-4 h-4 text-yellow-300" />
                  Process & Build Curriculum
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* VIEW 2: COURSE LIBRARY & CHAPTER OUTLINE INSPECTOR */}
      {activeTab === 'studio' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Course Selector List */}
          <div className="lg:col-span-4 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-sand-400 px-1">
              Available Courses ({courses.length})
            </h3>
            
            <div className="space-y-2.5 max-h-[680px] overflow-y-auto custom-scrollbar pr-1">
              {courses.map((c) => {
                const isSelected = activeCourse && activeCourse.course_id === c.course_id;
                const isCustom = !c.is_builtin;

                return (
                  <div
                    key={c.course_id}
                    onClick={() => onSelectCourse(c)}
                    className={`p-4 rounded-2xl border cursor-pointer transition-all duration-200 ${
                      isSelected
                        ? 'bg-sand-900 border-clay-500/60 shadow-xl shadow-sand-300/25'
                        : 'bg-sand-900/40 border-sand-800/80 hover:bg-sand-900/80 hover:border-sand-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div>
                        <div className="flex items-center gap-1.5 mb-1">
                          {isCustom ? (
                            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-clay-500/20 text-clay-300 border border-clay-500/30">
                              Custom Ingested
                            </span>
                          ) : (
                            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-ember-500/20 text-ember-300 border border-ember-500/30">
                              Standard
                            </span>
                          )}
                          <span className="text-[10px] text-sand-400 font-mono">
                            {c.subject} • {c.academic_tier}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-sand-50 line-clamp-1">{c.title}</h4>
                      </div>

                      {isCustom && onDeleteCourse && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (window.confirm(`Delete custom course "${c.title}"?`)) {
                              onDeleteCourse(c.course_id);
                            }
                          }}
                          title="Delete course"
                          className="p-1.5 text-sand-500 hover:text-clay-400 rounded-lg hover:bg-clay-950/30 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    <div className="flex items-center gap-3 text-[11px] text-sand-400 pt-2 border-t border-sand-800/60 font-mono">
                      <span>{c.chapters_count || c.chapters?.length || 1} Chapters</span>
                      <span>•</span>
                      <span>{c.flashcards_count || c.cards?.length || 0} Flashcards</span>
                      <span>•</span>
                      <span>{c.quizzes_count || c.quizzes?.length || 0} Quizzes</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Active Course Chapter Breakdown */}
          <div className="lg:col-span-8">
            {activeCourse ? (
              <div className="glass-panel p-6 rounded-2xl border border-sand-800 space-y-6">
                {/* Course Header Banner */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-sand-800">
                  <div>
                    <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-clay-400 block mb-1">
                      {activeCourse.is_builtin ? 'Standard Curriculum Repository' : 'Custom Ingested Course'}
                    </span>
                    <h3 className="text-xl font-extrabold text-sand-50">{activeCourse.title}</h3>
                    <p className="text-xs text-sand-400 mt-1">
                      {activeCourse.description || `Comprehensive learning module for ${activeCourse.title}.`}
                    </p>
                  </div>

                  {/* Navigation Shortcuts */}
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={onNavigateToStudy}
                      className="px-4 py-2 bg-gradient-to-r from-clay-600 to-amber-600 hover:from-clay-500 hover:to-amber-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-sand-300/25 transition flex items-center gap-1.5"
                    >
                      <BookOpen className="w-3.5 h-3.5" />
                      Study Flashcards
                    </button>
                    <button
                      onClick={onNavigateToPractice}
                      className="px-4 py-2 bg-sand-800 hover:bg-sand-700 text-sand-50 text-xs font-bold rounded-xl border border-sand-700 transition flex items-center gap-1.5"
                    >
                      <BrainCircuit className="w-3.5 h-3.5 text-olive-400" />
                      Practice Lab
                    </button>
                  </div>
                </div>

                {/* Chapter Cards Grid */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-sand-300 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-clay-400" />
                      Structured Theory Chapters ({activeCourse.chapters?.length || 1})
                    </h4>
                  </div>

                  <div className="space-y-3">
                    {(activeCourse.chapters || []).map((ch, idx) => {
                      const chIndex = ch.chapter_index || idx + 1;
                      return (
                        <div
                          key={ch.chapter_id || idx}
                          className="bg-sand-900/60 border border-sand-800 rounded-xl p-4 hover:border-sand-700 transition"
                        >
                          <div className="flex items-start justify-between gap-3 mb-2">
                            <div className="flex items-center gap-2.5">
                              <span className="w-6 h-6 rounded-lg bg-clay-500/20 text-clay-300 font-mono text-xs font-bold flex items-center justify-center border border-clay-500/30">
                                {chIndex}
                              </span>
                              <h5 className="text-sm font-bold text-sand-50">{ch.title}</h5>
                            </div>
                            <span className="text-[10px] font-mono text-sand-400 bg-sand-950 px-2 py-0.5 rounded border border-sand-800">
                              {(ch.cards || []).length} Flashcards
                            </span>
                          </div>

                          <p className="text-xs text-sand-300 leading-relaxed mb-3 pl-8">
                            {ch.summary || 'Essential theoretical principles and governing relationships.'}
                          </p>

                          {ch.objectives && ch.objectives.length > 0 && (
                            <div className="pl-8 pt-2 border-t border-sand-800/60 flex flex-wrap gap-2">
                              {ch.objectives.map((obj, oIdx) => (
                                <span
                                  key={oIdx}
                                  className="text-[10px] bg-sand-950/80 text-sand-400 px-2.5 py-1 rounded-lg border border-sand-800/80 flex items-center gap-1.5"
                                >
                                  <Check className="w-3 h-3 text-olive-400 shrink-0" />
                                  <span>{obj}</span>
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <div className="glass-panel p-12 text-center rounded-2xl border border-sand-800 text-sand-500 text-xs">
                No course selected. Ingest a material or pick a course from the library.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
