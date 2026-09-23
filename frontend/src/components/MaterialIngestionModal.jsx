import React, { useState, useEffect, useRef } from 'react';
import { 
  Upload, 
  FileText, 
  Sparkles, 
  X, 
  CheckCircle2, 
  AlertCircle, 
  Layers, 
  BookOpen, 
  Cpu, 
  BrainCircuit, 
  Loader2, 
  FileCheck,
  ChevronRight,
  Clock
} from 'lucide-react';

const SUBJECT_OPTIONS = ['Physics', 'Biology', 'Mathematics', 'Computer Science', 'General Science', 'Engineering'];
const TIER_OPTIONS = ['Class 10', 'Class 11-12', 'Undergraduate', 'Graduate', 'Professional'];

export default function MaterialIngestionModal({ isOpen, onClose, onIngestionSuccess }) {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'text'
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('Physics');
  const [tier, setTier] = useState('Undergraduate');
  const [rawText, setRawText] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  
  // Pipeline status
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState(0);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successCourse, setSuccessCourse] = useState(null);

  const fileInputRef = useRef(null);

  useEffect(() => {
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!title.trim()) {
      setErrorMsg('Please provide a course title.');
      return;
    }

    if (activeTab === 'upload' && !selectedFile) {
      setErrorMsg('Please select a PDF, TXT, or Markdown document to upload.');
      return;
    }

    if (activeTab === 'text' && rawText.trim().length < 50) {
      setErrorMsg('Please paste at least 50 characters of material text.');
      return;
    }

    setIsProcessing(true);
    setProcessingStep(1);

    try {
      // Smooth advance across visual steps
      const stepTimer1 = setTimeout(() => setProcessingStep(2), 1200);
      const stepTimer2 = setTimeout(() => setProcessingStep(3), 3200);
      const stepTimer3 = setTimeout(() => setProcessingStep(4), 5800);

      let response;
      if (activeTab === 'upload') {
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

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      clearTimeout(stepTimer3);

      if (!response.ok) {
        let errMessage = `Server error (${response.status})`;
        try {
          const err = await response.json();
          errMessage = err.detail || err.message || errMessage;
        } catch {
          errMessage = `Server returned status ${response.status}: ${response.statusText || 'Endpoint unavailable'}`;
        }
        throw new Error(errMessage);
      }

      const data = await response.json();
      setProcessingStep(5);
      setSuccessCourse(data.course);

      setTimeout(() => {
        setIsProcessing(false);
        setProcessingStep(0);
        setTitle('');
        setRawText('');
        setSelectedFile(null);
        if (onIngestionSuccess) {
          onIngestionSuccess(data.course);
        }
      }, 1000);

    } catch (err) {
      console.error("Ingestion submit error:", err);
      let message = err.message || 'An error occurred during material processing.';
      if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
        message = 'Could not connect to backend server. Please verify backend is running on http://127.0.0.1:8000.';
      }
      setErrorMsg(message);
      setIsProcessing(false);
      setProcessingStep(0);
    }
  };

  const steps = [
    { label: 'Parsing & Sanitizing Source Material', icon: FileText, desc: 'Extracting pages, stripping artifacts & noise' },
    { label: 'Structuring Chapter & Topic Outlines', icon: Layers, desc: 'Detecting sections & isolating core theory' },
    { label: 'Synthesizing Theory & Flashcards', icon: BookOpen, desc: 'Generating structured flashcards & takeaways' },
    { label: 'Vectorizing Embeddings into ChromaDB', icon: Cpu, desc: 'Indexing semantic knowledge chunks' },
    { label: 'Generating Practice Quizzes & Final Exam', icon: BrainCircuit, desc: 'Synthesizing evaluation question bank' },
  ];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-sand-50/65 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-2xl bg-sand-900 border border-clay-500/20 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-sand-800 bg-sand-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-clay-500/20 text-clay-400 rounded-xl">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-sand-50">Ingest Custom Material & Create Course</h3>
              <p className="text-xs text-sand-400">Transform documents, notes, or syllabi into chapters, flashcards & tests</p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            disabled={isProcessing}
            className="text-sand-400 hover:text-sand-50 p-1 rounded-lg hover:bg-sand-800 transition disabled:opacity-40"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Area */}
        <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
          {isProcessing ? (
            /* Animated Ingestion Pipeline View */
            <div className="py-4 flex flex-col items-center justify-center text-center">
              <div className="relative mb-5">
                <div className="w-20 h-20 rounded-full border-4 border-clay-500/20 border-t-clay-500 animate-spin flex items-center justify-center">
                  <BrainCircuit className="w-8 h-8 text-clay-400 animate-pulse" />
                </div>
              </div>

              <h4 className="text-lg font-bold text-sand-50 mb-1">Building Your Custom Learning Engine</h4>
              <p className="text-xs text-sand-400 mb-4 max-w-md">
                Decomposing material, synthesizing theory flashcards, vectorizing semantic knowledge, and engineering assessment questions.
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
                            : 'bg-sand-800/40 border-sand-800 text-sand-500'
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

              {elapsedSec > 10 && !successCourse && (
                <p className="text-[11px] text-sand-500 font-mono italic max-w-md">
                  💡 Processing extensive multi-page textbook/paper. Generating high-retention flashcards and embedding vector database...
                </p>
              )}

              {successCourse && (
                <div className="mt-6 flex items-center gap-2 text-olive-400 text-sm font-semibold animate-fadeIn">
                  <CheckCircle2 className="w-5 h-5" />
                  <span>Course Generated! Launching Dashboard...</span>
                </div>
              )}
            </div>
          ) : (
            /* Input Form */
            <form onSubmit={handleSubmit} className="space-y-5">
              {errorMsg && (
                <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-700 text-xs">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* Mode Tabs */}
              <div className="flex bg-sand-800/80 p-1 rounded-xl border border-sand-700/50">
                <button
                  type="button"
                  onClick={() => setActiveTab('upload')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-semibold rounded-lg transition ${
                    activeTab === 'upload' ? 'bg-clay-600 text-white shadow-md' : 'text-sand-400 hover:text-sand-200'
                  }`}
                >
                  <Upload className="w-3.5 h-3.5" />
                  Upload Document (PDF / TXT / MD)
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('text')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-semibold rounded-lg transition ${
                    activeTab === 'text' ? 'bg-clay-600 text-white shadow-md' : 'text-sand-400 hover:text-sand-200'
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" />
                  Paste Notes / Syllabus Text
                </button>
              </div>

              {/* Title & Metadata Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="md:col-span-3">
                  <label className="block text-[11px] font-medium uppercase tracking-wider text-sand-400 mb-1">
                    Course / Topic Title *
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Organic Chemistry Module 1, Classical Mechanics"
                    className="w-full bg-sand-950 border border-sand-800 rounded-xl px-3.5 py-2 text-xs text-sand-50 placeholder-sand-500 focus:outline-none focus:border-clay-500"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-medium uppercase tracking-wider text-sand-400 mb-1">
                    Subject Field
                  </label>
                  <select
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="w-full bg-sand-950 border border-sand-800 rounded-xl px-3 py-2 text-xs text-sand-50 focus:outline-none focus:border-clay-500"
                  >
                    {SUBJECT_OPTIONS.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>

                <div className="md:col-span-2">
                  <label className="block text-[11px] font-medium uppercase tracking-wider text-sand-400 mb-1">
                    Target Academic Level
                  </label>
                  <select
                    value={tier}
                    onChange={(e) => setTier(e.target.value)}
                    className="w-full bg-sand-950 border border-sand-800 rounded-xl px-3 py-2 text-xs text-sand-50 focus:outline-none focus:border-clay-500"
                  >
                    {TIER_OPTIONS.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Source Document or Text Area */}
              {activeTab === 'upload' ? (
                <div>
                  <label className="block text-[11px] font-medium uppercase tracking-wider text-sand-400 mb-1">
                    Source Document (PDF, TXT, MD) *
                  </label>
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleFileDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition flex flex-col items-center justify-center ${
                      selectedFile 
                        ? 'border-olive-500/50 bg-olive-500/5 text-olive-300' 
                        : 'border-sand-700 hover:border-clay-500 bg-sand-950/40 hover:bg-sand-950/80'
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
                      <div className="flex items-center gap-3">
                        <FileCheck className="w-8 h-8 text-olive-400" />
                        <div className="text-left">
                          <div className="text-xs font-semibold text-sand-50">{selectedFile.name}</div>
                          <div className="text-[10px] text-olive-400">
                            {(selectedFile.size / 1024).toFixed(1)} KB • Ready for extraction
                          </div>
                        </div>
                      </div>
                    ) : (
                      <>
                        <Upload className="w-8 h-8 text-sand-400 mb-2" />
                        <div className="text-xs font-medium text-sand-300">Click to browse or drag & drop document</div>
                        <div className="text-[10px] text-sand-500 mt-0.5">PDF research papers, textbooks (.pdf), text (.txt), markdown (.md)</div>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div>
                  <label className="block text-[11px] font-medium uppercase tracking-wider text-sand-400 mb-1">
                    Paste Lecture Notes, Syllabus, or Book Sections *
                  </label>
                  <textarea
                    value={rawText}
                    onChange={(e) => setRawText(e.target.value)}
                    rows={6}
                    placeholder="Paste lecture notes or chapter contents here... (e.g. Chapter 1: ..., Chapter 2: ...)"
                    className="w-full bg-sand-950 border border-sand-800 rounded-xl p-3 text-xs text-sand-50 placeholder-sand-500 focus:outline-none focus:border-clay-500 font-mono"
                  />
                  <div className="text-right text-[10px] text-sand-500 mt-1">{rawText.length} characters</div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-sand-400 hover:text-sand-50 hover:bg-sand-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-clay-600 to-ember-600 hover:from-clay-500 hover:to-ember-500 shadow-lg shadow-sand-300/25 transition active:scale-95"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Process & Generate Course
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
