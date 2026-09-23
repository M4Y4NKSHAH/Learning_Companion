import React, { useState, useEffect } from 'react';
import Reveal from './Reveal';
import { 
  BrainCircuit, 
  ChevronRight, 
  ChevronLeft,
  ArrowRight, 
  Zap, 
  Sparkles,
  BookOpen,
  HelpCircle,
  Bookmark,
  Layout,
  Instagram,
  Facebook,
  Twitter,
  Menu,
  X,
  Dna,
  Atom,
  Binary,
  GraduationCap,
  School,
  Library,
  Check
} from 'lucide-react';

import heroImage from '../assets/heroImage.png';
import gallery1 from '../assets/gallery1.png';
import gallery2 from '../assets/gallery2.png';
import gallery3 from '../assets/gallery3.png';
import gallery4 from '../assets/gallery4.png';
import gallery5 from '../assets/gallery5.png';

export default function LandingPage({ onSignUp, onNavigateSubject, onNavigateTier, onStartLearning, onOpenIngestion }) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [selectionModalOpen, setSelectionModalOpen] = useState(false);
  const [pendingSelections, setPendingSelections] = useState({ subject: null, tier: null });
  const [modalError, setModalError] = useState('');
  const [galleryIndex, setGalleryIndex] = useState(null); // null = lightbox closed

  const galleryImages = [
    { src: gallery1, alt: 'Learning experience preview' },
    { src: gallery2, alt: 'Gallery preview 2' },
    { src: gallery3, alt: 'Gallery preview 3' },
    { src: gallery4, alt: 'Gallery preview 4' },
    { src: gallery5, alt: 'Gallery preview 5' }
  ];

  const openGallery = (index) => setGalleryIndex(index);
  const closeGallery = () => setGalleryIndex(null);
  const prevImage = () => setGalleryIndex(prev => (prev === null ? prev : (prev - 1 + galleryImages.length) % galleryImages.length));
  const nextImage = () => setGalleryIndex(prev => (prev === null ? prev : (prev + 1) % galleryImages.length));

  // Opens the "choose your class" modal for a subject card
  const handleExploreCourse = (subject) => {
    setPendingSelections({ subject, tier: null });
    setModalError('');
    setSelectionModalOpen(true);
  };

  // Opens the modal for a tier card to confirm subject + class
  const handleSelectTier = (tier) => {
    setPendingSelections({ subject: null, tier });
    setModalError('');
    setSelectionModalOpen(true);
  };

  // Launch the dashboard once both subject and tier are selected
  const confirmSelection = () => {
    if (onStartLearning && pendingSelections.subject && pendingSelections.tier) {
      setSelectionModalOpen(false);
      setModalError('');
      onStartLearning(pendingSelections.subject, pendingSelections.tier);
    } else if (onNavigateSubject && pendingSelections.subject) {
      // Fallback to old behavior if new prop missing
      setSelectionModalOpen(false);
      onNavigateSubject(pendingSelections.subject);
    } else if (onNavigateTier && pendingSelections.tier) {
      setSelectionModalOpen(false);
      onNavigateTier(pendingSelections.tier);
    } else {
      setModalError('Please choose both a subject and a class before continuing.');
    }
  };

  const closeModal = () => {
    setSelectionModalOpen(false);
    setModalError('');
  };

  const scrollToSection = (id) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
    setIsMenuOpen(false);
  };

  // Keyboard navigation for the gallery lightbox
  useEffect(() => {
    if (galleryIndex === null) return;
    const onKey = (e) => {
      if (e.key === 'Escape') closeGallery();
      else if (e.key === 'ArrowLeft') prevImage();
      else if (e.key === 'ArrowRight') nextImage();
    };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden'; // prevent background scroll
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [galleryIndex]);

  const subjects = [
    { icon: Atom, title: "Physics", desc: "Master the laws of nature from classical mechanics to quantum formulations with interactive RAG-powered modules." },
    { icon: Dna, title: "Biology", desc: "Explore the complexities of life, from cellular power plants to advanced epigenetic modifications and genetics." },
    { icon: Binary, title: "Mathematics", desc: "Build a strong foundation in calculus, linear equations, and analytical transformations through Socratic guidance." }
  ];

  const levels = [
    { icon: School, title: "Class 10", desc: "Foundational concepts designed to prepare students for early academic excellence and core understanding." },
    { icon: Library, title: "Class 11-12", desc: "Advanced high-school curriculum focused on preparing students for university-level challenges and entrance exams." },
    { icon: GraduationCap, title: "Undergraduate", desc: "Rigorous academic content tailored for university students pursuing degrees in science and mathematics." }
  ];

  return (
    <div className="min-h-screen bg-sand-950 text-sand-100 flex flex-col font-sans antialiased overflow-x-hidden selection:bg-ember-500 selection:text-white">
      {/* GLOWING ORB DECORATIONS — now floating */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-ember-500/5 blur-[120px] pointer-events-none animate-float"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] rounded-full bg-clay-500/5 blur-[120px] pointer-events-none animate-float-slow"></div>

      {/* TOP HEADER */}
      <header className="w-full glass-panel border-b border-sand-900 px-6 py-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-tr from-ember-600 to-clay-600 p-2 rounded-xl shadow-lg shadow-sand-300/25">
            <BrainCircuit className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-sm font-bold tracking-tight bg-gradient-to-r from-sand-50 to-sand-400 bg-clip-text text-transparent">AURA</h1>
        </div>
        
        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-8 text-xs font-medium text-sand-400">
          <button onClick={() => scrollToSection('features')} className="hover:text-sand-50 transition-colors">Features</button>
          <button onClick={() => scrollToSection('offerings')} className="hover:text-sand-50 transition-colors">Offerings</button>
          <button onClick={() => scrollToSection('gallery')} className="hover:text-sand-50 transition-colors">Gallery</button>
          <button onClick={() => scrollToSection('about')} className="hover:text-sand-50 transition-colors">About</button>
        </nav>

        <div className="flex items-center gap-4">
          <button 
            onClick={onSignUp}
            className="hidden sm:block bg-sand-100 text-sand-950 text-xs font-bold px-5 py-2 rounded-lg hover:bg-sand-50 transition-all shadow-lg"
          >
            Sign Up
          </button>
          
          {/* Hamburger Menu Button */}
          <button 
            className="md:hidden text-sand-400 hover:text-sand-50 transition-colors"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile Menu Overlay */}
        {isMenuOpen && (
          <div className="absolute top-full left-0 w-full bg-sand-950/95 backdrop-blur-xl border-b border-sand-900 md:hidden flex flex-col p-6 space-y-6 z-40 animate-fadeIn">
            <button onClick={() => scrollToSection('features')} className="text-left text-sm font-semibold text-sand-300 hover:text-sand-50">Features</button>
            <button onClick={() => scrollToSection('offerings')} className="text-left text-sm font-semibold text-sand-300 hover:text-sand-50">Offerings</button>
            <button onClick={() => scrollToSection('gallery')} className="text-left text-sm font-semibold text-sand-300 hover:text-sand-50">Gallery</button>
            <button onClick={() => scrollToSection('about')} className="text-left text-sm font-semibold text-sand-300 hover:text-sand-50">About</button>
            <button 
              onClick={onSignUp}
              className="w-full bg-ember-600 text-white font-bold py-3 rounded-xl"
            >
              Get Started
            </button>
          </div>
        )}
      </header>

      <main className="flex-1 max-w-[1200px] mx-auto px-6 py-12 space-y-32">
        
        {/* HERO SECTION */}
        <section id="about" className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center pt-12">
          <Reveal direction="right" className="space-y-6">
            <h2 className="text-5xl font-extrabold leading-tight tracking-tight text-sand-50">
              Elevate Your Learning with <span className="bg-gradient-to-r from-ember-400 to-clay-500 bg-clip-text text-transparent animate-gradient-text">AI Intelligence</span>
            </h2>
            <p className="text-lg text-sand-400 max-w-lg leading-relaxed">
              Experience a cognitive companion that adapts to your unique learning style. 
              Master complex subjects with RAG-powered study decks and real-time Socratic feedback.
            </p>
            <div className="flex flex-wrap items-center gap-4">
              <button 
                onClick={onSignUp}
                className="bg-ember-600 hover:bg-ember-500 text-white font-bold text-sm px-6 py-3 rounded-xl shadow-lg shadow-sand-300/25 transition-all flex items-center gap-2"
              >
                Get Started <ArrowRight className="w-4 h-4" />
              </button>
              {onOpenIngestion && (
                <button 
                  onClick={onOpenIngestion}
                  className="bg-gradient-to-r from-clay-600 to-amber-600 hover:from-clay-500 hover:to-amber-500 text-white font-bold text-sm px-5 py-3 rounded-xl shadow-lg shadow-sand-300/25 transition-all flex items-center gap-2"
                >
                  <Sparkles className="w-4 h-4" /> Ingest Your Notes & Tests
                </button>
              )}
              <button 
                onClick={() => scrollToSection('features')}
                className="bg-sand-900/50 border border-sand-800 hover:bg-sand-800 text-sand-50 font-bold text-sm px-5 py-3 rounded-xl transition-all"
              >
                Learn More
              </button>
            </div>
          </Reveal>
          <Reveal direction="left" delay={150}>
            <div className="glass-panel aspect-video rounded-3xl border border-sand-800 flex items-center justify-center bg-sand-900/40 relative group overflow-hidden">
               <div className="absolute inset-0 bg-gradient-to-tr from-ember-500/10 to-clay-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-700 animate-glow-pulse"></div>
               <img src={heroImage} alt="Aura cognitive learning companion hero illustration" className="w-full h-full object-cover japandi-plate" />
            </div>
          </Reveal>
        </section>

        {/* FEATURES GRID SECTION */}
        <section id="features" className="space-y-12 text-center scroll-mt-24">
          <Reveal direction="up">
            <div className="space-y-4">
              <h3 className="text-3xl font-bold text-sand-50">Advanced Learning Modules</h3>
              <p className="text-sand-400 max-w-2xl mx-auto">
                Our platform combines cognitive science with state-of-the-art AI to provide an unparalleled educational experience.
              </p>
            </div>
          </Reveal>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { id: 'rag', icon: BookOpen, title: "Study Decks", desc: "RAG-powered intelligent flashcards that summarize complex textbooks into digestible bits." },
              { id: 'socratic', icon: HelpCircle, title: "Practice Lab", desc: "Interactive Socratic dialogue that guides you to solutions rather than just giving answers." },
              { id: 'threshold', icon: Bookmark, title: "Threshold Exams", desc: "Adaptive testing that measures mastery and identifies conceptual gaps using fuzzy logic." },
              { id: 'spaced', icon: Zap, title: "Quick Recall", desc: "Optimized spaced repetition algorithms to ensure long-term retention of critical concepts." },
              { id: 'genai', icon: Sparkles, title: "AI Generation", desc: "Instantly create study materials from any textbook or curriculum with one click." },
              { id: 'glassbox', icon: Layout, title: "Glassbox UI", desc: "Transparent, distraction-free interface designed for deep focus and peak productivity." }
            ].map((f, i) => (
              <Reveal key={i} direction="scale" delay={i * 80} className="h-full">
                <div className="glass-panel p-8 rounded-2xl border border-sand-900 hover:border-ember-500/30 transition-all text-left space-y-4 group relative overflow-hidden animate-shimmer h-full">
                  <div className="w-10 h-10 rounded-xl bg-sand-900 border border-sand-800 flex items-center justify-center text-ember-400 group-hover:scale-110 transition-transform">
                    <f.icon className="w-5 h-5" />
                  </div>
                  <h4 className="text-lg font-bold text-sand-50">{f.title}</h4>
                  <p className="text-sm text-sand-400 leading-relaxed">{f.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* IMAGE GALLERY SECTION */}
        <section id="gallery" className="space-y-12 scroll-mt-24">
          <Reveal direction="up">
            <h3 className="text-3xl font-bold text-sand-50 text-center">Visual Learning Journey</h3>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:h-[600px]">
            <Reveal direction="right" delay={100} className="h-full">
              <button
                type="button"
                onClick={() => openGallery(0)}
                className="glass-panel rounded-3xl border border-sand-800 bg-sand-900/40 flex items-center justify-center relative group overflow-hidden h-72 md:h-full w-full cursor-pointer text-left"
              >
                 <div className="absolute inset-0 bg-gradient-to-br from-ember-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity animate-glow-pulse"></div>
                 <img src={gallery1} alt="Learning experience preview" className="w-full h-full object-cover japandi-plate" />
                 {/* Click-to-view overlay on gallery1 */}
                 <div className="absolute inset-0 flex items-end justify-center pointer-events-none bg-gradient-to-t from-sand-50/70 via-sand-50/10 to-transparent p-5">
                   <span className="text-sm md:text-base font-semibold text-sand-50 bg-sand-900/70 backdrop-blur-sm border border-sand-800 px-4 py-2 rounded-full flex items-center gap-2">
                     <Layout className="w-4 h-4" /> Click to View Image
                   </span>
                 </div>
              </button>
            </Reveal>
            <div className="grid grid-cols-2 grid-rows-2 gap-6">
              {galleryImages.slice(1).map((g, i) => (
                <Reveal key={i} direction="scale" delay={150 + i * 60} className="h-full">
                  <button
                    type="button"
                    onClick={() => openGallery(i + 1)}
                    className="glass-panel rounded-2xl border border-sand-800 bg-sand-900/40 flex items-center justify-center relative group overflow-hidden h-44 md:h-full w-full cursor-pointer text-left"
                  >
                    <div className="absolute inset-0 bg-gradient-to-br from-clay-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    <img src={g.src} alt={g.alt} className="w-full h-full object-cover japandi-plate" />
                    <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none bg-sand-50/30">
                      <span className="text-xs font-semibold text-sand-50 bg-sand-900/70 backdrop-blur-sm border border-sand-800 px-3 py-1.5 rounded-full">
                        View Image
                      </span>
                    </div>
                  </button>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* OFFERINGS SECTION (2x3 GRID: SUBJECTS & LEVELS) */}
        <section id="offerings" className="space-y-16 scroll-mt-24">
          <Reveal direction="up">
            <div className="text-center space-y-4">
              <h3 className="text-3xl font-bold text-sand-50">Explore Our Curriculum</h3>
              <p className="text-sand-400 max-w-2xl mx-auto">
                Choose a subject then select your class to launch your personal Aura dashboard.
              </p>
            </div>
          </Reveal>

          <div className="space-y-12">
            {/* Subjects Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {subjects.map((s, i) => (
                <Reveal key={i} direction="scale" delay={i * 90} className="h-full">
                  <div className="glass-panel p-8 rounded-2xl border border-sand-900 hover:border-olive-500/30 transition-all space-y-4 group relative overflow-hidden animate-shimmer h-full flex flex-col">
                    <div className="w-12 h-12 rounded-xl bg-sand-900 border border-sand-800 flex items-center justify-center text-olive-400 group-hover:scale-110 transition-transform">
                      <s.icon className="w-6 h-6" />
                    </div>
                    <h4 className="text-xl font-bold text-sand-50">{s.title}</h4>
                    <p className="text-sm text-sand-400 leading-relaxed flex-1">{s.desc}</p>
                    <button 
                      onClick={() => handleExploreCourse(s.title)}
                      className="text-xs font-bold text-olive-400 flex items-center gap-1 hover:gap-2 transition-all"
                    >
                      Explore Course <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                </Reveal>
              ))}
            </div>

            {/* Academic Levels Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {levels.map((l, i) => (
                <Reveal key={i} direction="scale" delay={i * 90} className="h-full">
                  <div className="glass-panel p-8 rounded-2xl border border-sand-900 hover:border-clay-500/30 transition-all space-y-4 group relative overflow-hidden animate-shimmer h-full flex flex-col">
                    <div className="w-12 h-12 rounded-xl bg-sand-900 border border-sand-800 flex items-center justify-center text-clay-400 group-hover:scale-110 transition-transform">
                      <l.icon className="w-6 h-6" />
                    </div>
                    <h4 className="text-xl font-bold text-sand-50">{l.title}</h4>
                    <p className="text-sm text-sand-400 leading-relaxed flex-1">{l.desc}</p>
                    <button 
                      onClick={() => handleSelectTier(l.title)}
                      className="text-xs font-bold text-clay-400 flex items-center gap-1 hover:gap-2 transition-all"
                    >
                      Select Tier <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* FINAL HERO SECTION */}
        <Reveal direction="up">
          <section className="text-center py-20 glass-panel rounded-[40px] border border-sand-900 relative overflow-hidden">
             <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-ember-500/5 blur-[100px] rounded-full animate-glow-pulse"></div>
             <div className="relative z-10 space-y-8 max-w-3xl mx-auto px-6">
                <h3 className="text-4xl font-bold text-sand-50">Ready to Transform Your Learning?</h3>
                <p className="text-sand-400 text-lg">
                  Join thousands of students using Aura to accelerate their education. 
                  Experience the future of personalized tutoring today.
                </p>
                <div className="flex flex-wrap justify-center gap-4">
                  <button 
                    onClick={onSignUp}
                    className="bg-sand-100 text-sand-950 font-bold text-sm px-8 py-4 rounded-2xl hover:bg-sand-50 transition-all shadow-xl shadow-sand-300/20"
                  >
                    Get Started for Free
                  </button>
                  <button 
                    onClick={() => scrollToSection('about')}
                    className="bg-sand-950 border border-sand-800 text-sand-50 font-bold text-sm px-8 py-4 rounded-2xl hover:bg-sand-900 transition-all"
                  >
                    Contact Support
                  </button>
                </div>
             </div>
          </section>
        </Reveal>

      </main>

      {/* FOOTER */}
      <footer className="w-full border-t border-sand-900 bg-sand-950/80 backdrop-blur-md px-6 py-12">
        <div className="max-w-[1200px] mx-auto space-y-12">
          <div className="flex flex-col md:flex-row justify-between items-center gap-8">
            <div className="flex items-center gap-3">
              <div className="bg-sand-800 p-2 rounded-lg">
                <BrainCircuit className="w-4 h-4 text-sand-50" />
              </div>
              <span className="font-bold text-sand-50 tracking-tight">AURA</span>
            </div>
            
            <div className="flex gap-8 text-xs font-medium text-sand-500">
              <button onClick={() => scrollToSection('about')} className="hover:text-sand-300">About</button>
              <a href="#" className="hover:text-sand-300">Privacy</a>
              <a href="#" className="hover:text-sand-300">Terms</a>
              <a href="#" className="hover:text-sand-300">Contact</a>
            </div>

            <div className="flex gap-4">
              <Instagram className="w-4 h-4 text-sand-500 hover:text-sand-50 cursor-pointer transition-colors" />
              <Facebook className="w-4 h-4 text-sand-500 hover:text-sand-50 cursor-pointer transition-colors" />
              <Twitter className="w-4 h-4 text-sand-500 hover:text-sand-50 cursor-pointer transition-colors" />
            </div>
          </div>
          
          <div className="flex flex-col md:flex-row justify-between items-center pt-8 border-t border-sand-900/50 gap-4 text-[10px] font-mono text-sand-600 uppercase tracking-widest">
            <span>© 2024 Aura Cognitive. All rights reserved.</span>
            <div className="flex gap-6">
              <a href="#" className="hover:text-sand-400">Privacy Policy</a>
              <a href="#" className="hover:text-sand-400">Terms of Service</a>
            </div>
          </div>
        </div>
      </footer>

      {/* CLASS SELECTION MODAL */}
      {selectionModalOpen && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-sand-50/65 backdrop-blur-sm animate-fadeIn"
          onClick={closeModal}
        >
          <div 
            className="glass-panel relative w-full max-w-lg p-8 rounded-3xl border border-sand-800 shadow-2xl animate-fadeIn"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={closeModal}
              className="absolute top-4 right-4 text-sand-500 hover:text-sand-50 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 mb-2">
              <div className="bg-gradient-to-tr from-ember-600 to-clay-600 p-2.5 rounded-xl">
                <BrainCircuit className="w-5 h-5 text-white" />
              </div>
              <h3 className="text-lg font-bold text-sand-50">Choose Your Learning Path</h3>
            </div>
            <p className="text-xs text-sand-400 mb-6">
              Select your subject and class to launch your personalized Aura dashboard.
            </p>

            <div className="space-y-5">
              {/* SUBJECT SELECTION */}
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-sand-500 block mb-2">Subject</span>
                <div className="grid grid-cols-3 gap-2">
                  {subjects.map(s => (
                    <button
                      key={s.title}
                      onClick={() => setPendingSelections(prev => ({ ...prev, subject: s.title }))}
                      className={`p-3 rounded-xl border text-xs font-semibold transition-all flex flex-col items-center gap-1.5 ${pendingSelections.subject === s.title ? 'bg-olive-500/15 border-olive-500/50 text-olive-300' : 'bg-sand-900/60 border-sand-800 text-sand-400 hover:border-sand-600 hover:text-sand-200'}`}
                    >
                      <s.icon className="w-4 h-4" />
                      {s.title}
                      {pendingSelections.subject === s.title && <Check className="w-3.5 h-3.5 text-olive-400" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* TIER SELECTION */}
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-sand-500 block mb-2">Class / Academic Level</span>
                <div className="grid grid-cols-3 gap-2">
                  {levels.map(l => (
                    <button
                      key={l.title}
                      onClick={() => setPendingSelections(prev => ({ ...prev, tier: l.title }))}
                      className={`p-3 rounded-xl border text-xs font-semibold transition-all flex flex-col items-center gap-1.5 ${pendingSelections.tier === l.title ? 'bg-clay-500/15 border-clay-500/50 text-clay-300' : 'bg-sand-900/60 border-sand-800 text-sand-400 hover:border-sand-600 hover:text-sand-200'}`}
                    >
                      <l.icon className="w-4 h-4" />
                      {l.title}
                      {pendingSelections.tier === l.title && <Check className="w-3.5 h-3.5 text-clay-400" />}
                    </button>
                  ))}
                </div>
              </div>

              {modalError && (
                <p className="text-xs text-amber-800 bg-amber-500/10 border border-amber-500/40 rounded-lg px-3 py-2">
                  {modalError}
                </p>
              )}
            </div>

            <button 
              onClick={confirmSelection}
              disabled={!pendingSelections.subject || !pendingSelections.tier}
              className="w-full mt-6 bg-ember-600 hover:bg-ember-500 disabled:opacity-40 disabled:pointer-events-none text-white font-bold text-sm px-6 py-3 rounded-xl shadow-lg shadow-sand-300/25 transition-all flex items-center justify-center gap-2"
            >
              Launch Dashboard <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
{/* IMAGE CAROUSEL LIGHTBOX */}
      {galleryIndex !== null && (
        <div
          className="fixed inset-0 z-[120] flex items-center justify-center bg-sand-50/85 backdrop-blur-sm animate-fadeIn"
          onClick={closeGallery}
        >
          <button
            type="button"
            onClick={closeGallery}
            aria-label="Close carousel"
            className="absolute top-5 right-5 p-2.5 rounded-full bg-sand-900/80 border border-sand-700 text-sand-300 hover:text-sand-50 hover:bg-sand-800 transition-colors z-20"
          >
            <X className="w-5 h-5" />
          </button>

          {/* Prev arrow */}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); prevImage(); }}
            aria-label="Previous image"
            className="absolute left-3 md:left-8 top-1/2 -translate-y-1/2 p-3 rounded-full bg-sand-900/80 border border-sand-700 text-sand-200 hover:bg-sand-800 hover:text-sand-50 transition-all z-20 shadow-lg"
          >
            <ChevronLeft className="w-6 h-6" />
          </button>

          {/* Current image */}
          <div
            className="max-w-[90vw] max-h-[85vh] w-full mx-auto px-14 md:px-20 relative"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={galleryImages[galleryIndex].src}
              alt={galleryImages[galleryIndex].alt}
              className="w-full h-full max-h-[85vh] object-contain rounded-xl japandi-plate"
            />
            <div className="flex items-center justify-between gap-4 mt-4">
              <span className="text-xs font-mono text-sand-400 bg-sand-900/70 border border-sand-700/70 px-3 py-1 rounded-full">
                {galleryIndex + 1} / {galleryImages.length}
              </span>
              <span className="text-sm text-sand-200 bg-sand-900/70 border border-sand-700/70 px-4 py-1.5 rounded-full truncate max-w-[60%]">
                {galleryImages[galleryIndex].alt}
              </span>
            </div>
          </div>

          {/* Next arrow */}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); nextImage(); }}
            aria-label="Next image"
            className="absolute right-3 md:right-8 top-1/2 -translate-y-1/2 p-3 rounded-full bg-sand-900/80 border border-sand-700 text-sand-200 hover:bg-sand-800 hover:text-sand-50 transition-all z-20 shadow-lg"
          >
            <ChevronRight className="w-6 h-6" />
          </button>
        </div>
      )}
    </div>
  );
}
