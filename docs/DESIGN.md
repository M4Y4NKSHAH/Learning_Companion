# 🎨 Design — Learning Companion (AURA)

> Visual & interaction design reference for the frontend. Covers the Landing Page, the
> Glass-Box Dashboard, Course Studio, Pedagogical Guardrails, the design tokens, animations, and component inventory.

---

## 1. Design Overview

Three distinct surfaces share one visual language:

| Surface | File | Mood |
| --- | --- | --- |
| **Landing Page** | `src/components/LandingPage.jsx` | Marketing: hero, feature grid, offering cards, gallery lightbox |
| **Glass-Box Dashboard** | `src/App.jsx` | Telemetry: study deck, practice lab, exam, live "active node" readout, Socratic chat |
| **Course Studio** | `src/components/CourseStudioView.jsx` | Course Creation: drag-and-drop document upload, chapter decomposition, deep theory previews |

All surfaces use the **japandi / washi-paper** aesthetic: light rice-paper background, sumi-ink
typography, muted cedar→moss→clay accents, matte paper panels, soft diffused ink shadows,
and subtle float animations ("drifting wash" orbs in the hero).

---

## 2. Design Tokens

| Token | Value | Where used |
| --- | --- | --- |
| Background | `#EAE4D8` (`sand-950`) rice paper + two fixed radial washes (cedar 7%, moss 6%) | Body + all surfaces |
| Panel | `rgba(250,246,239,.78)` + `backdrop-filter: blur(10px) saturate(105%)` | `.glass-panel` |
| Panel border | `rgba(43,39,35,0.09)` ink hairline | `.glass-panel` border |
| Shadow | `0 14px 34px -26px rgba(43,39,35,.28)` (soft ink) | `.glass-panel`, cards |
| Font | `Outfit` (Google Fonts) + system-ui fallback | Entire app |
| Corner radius | `rounded-xl` / `rounded-2xl` | Cards, buttons, panels |
| Grid | 12-col for dashboard (`lg:grid-cols-12`) | App layout |
| Halo | `.glow-ember` `.glow-olive` `.glow-clay` (soft 18/44px halo @ 45%) | Active panels |
| Ring | `ringColor.DEFAULT` = `ember-500` | Focus rings |
| Focus | `:focus-visible` → 2px `rgba(165,98,58,.55)` outline, 2px offset | Keyboard nav |
| Selection | `::selection` ink `#2B2723` on washi `#F4EFE6` | Text selection |
| Shadow tokens | `shadow-japandi-sm` / `shadow-japandi` / `shadow-japandi-lg` | Opt-in soft depth |

### Japandi material scales (`frontend/tailwind.config.js` → `japandiPalette`)

| Family | Role | Anchor shades |
| --- | --- | --- |
| `sand` | Neutrals — paper, ink, hairline borders, body copy | `sand-950 #EAE4D8` (paper) → `sand-50 #1E1B18` (sumi ink) |
| `ember` | Primary accent — Physics, primary CTAs, brand gradients | `ember-500 #A5623A`, `ember-600 #9A5530` (hinoki cedar) |
| `olive` | Secondary accent — Biology, success/mastery states | `olive-500 #5E7A3E`, `olive-600 #556E38` (matcha moss) |
| `clay` | Tertiary accent — Mathematics, brand gradients, hints & alerts | `clay-500 #A85B56`, `clay-600 #9C524D` (raw clay) |
| `amber` / `yellow` | Warnings, hint badges, rating stars | `amber-500/10` border-amber-500/40 |
| `rose` | Course Guardrail deflections & prohibited off-topic alerts | `rose-950/70 border-rose-500/50 text-rose-300` |

---

## 3. Cognitive Badges & Chat Telemetry (`App.jsx`)

When the AI tutor responds, the message bubble renders an architectural telemetry badge reflecting the LangGraph active node and intent:

| Node Type | Badge Text | Styling Token |
| --- | --- | --- |
| `guardrail_deflection` | `🎯 Course Guardrail` | `bg-rose-950/70 border-rose-500/50 text-rose-300 font-semibold shadow-sm` |
| `deep` | `🔮 Deep Inquiry` | `bg-clay-950/60 border-clay-500/40 text-clay-300` |
| `solution` / `remedial` | `⚡ Direct Solution` | `bg-clay-950/60 border-clay-500/40 text-clay-300` |
| `hint` | `💡 Socratic Hint` | `bg-amber-500/10 border-amber-500/40 text-amber-800` |
| `surface` | `🌱 Concept Guide` | `bg-olive-950/60 border-olive-500/40 text-olive-300` |

In addition, each response includes a Mamdani Fuzzy Inference System indicator:
`FIS: 85%` rendered in `text-olive-400 bg-olive-950/40 border border-olive-500/30`.

---

## 4. Pedagogical Level Presentation

The UI formats explanations differently based on the learner's academic level:

### 4.1 Introductory (Class 9–10)
- **Tone**: Warm, encouraging, visual.
- **Math Formatting**: Plain readable ASCII math ($a = \frac{v - u}{t}$, $F = m \cdot a$). Complex LaTeX blocks ($\frac{d}{dx}, \int$) are strictly suppressed.
- **Visuals**: Intuitive real-world analogies (e.g. playground swings, bicycle gears, water pipes) are emphasized in prominent quote callouts.

### 4.2 Standard (Class 11–12)
- **Tone**: Analytical, structured, rigorous.
- **Math Formatting**: Formal equations with explicit parameter definitions and SI units.

### 4.3 Advanced (University / Undergraduate)
- **Tone**: Scholarly, concise, first-principles oriented.
- **Math Formatting**: Full state equations, boundary condition analyses, and invariant conservation proofs.

---

## 5. Course Studio & Ingestion Flow (`CourseStudioView.jsx`)

1. **Document Drag-and-Drop Area**:
   - Accepts `.pdf`, `.txt`, `.md`, or raw pasted text.
   - Live progress indicator with status steps: *Sanitizing* → *Detecting Chapters* → *Synthesizing Cards & Blueprints* → *Vector Ingestion*.
2. **Dynamic Chapter Navigator**:
   - Visual list of detected instructional chapters (no front/back matter clutter).
   - Live preview of synthesized theory summaries, learning objectives, and 3 high-impact flashcards per chapter.
3. **One-Click Course Launch**:
   - Ingested courses automatically appear in the user's workspace sidebar with custom badges.

---

## 6. Component Inventory

| Component | File | Purpose |
| --- | --- | --- |
| `LandingPage` | `components/LandingPage.jsx` | Marketing + onboarding flow with Japandi aesthetic |
| `Reveal` | `components/Reveal.jsx` | Scroll-triggered entrance animation wrapper |
| `App` | `App.jsx` | Dashboard shell, telemetry HUD, chat, practice lab, threshold exam |
| `CourseStudioView` | `components/CourseStudioView.jsx` | Dynamic curriculum creator & book ingestion studio |
| `MaterialIngestionModal` | `components/MaterialIngestionModal.jsx` | Modal dialog for instant custom document parsing |
| `ChapterNav` | `components/ChapterNav.jsx` | Dynamic chapter navigation bar with progress states |
| `TheoryExplorer` | `components/TheoryExplorer.jsx` | Interactive theory breakdown, mental models, axioms |
| `HintMarkdown` | `App.jsx` (internal) | Renders formatted markdown, code blocks, ASCII math |

---

## 7. Interaction Rules

**Do:**
- Keep all panels on the washi rice-paper palette (`sand-950`).
- Use the subject accent map (`ember` for Physics, `olive` for Biology, `clay` for Mathematics).
- Use `🎯 Course Guardrail` rose-tinted badges for deflected off-topic questions.
- Enforce plain text and ASCII math for Class 9–10 learners (no LaTeX clutter).

**Don't:**
- Introduce dark theme backgrounds or neon colors.
- Reveal answers directly in Socratic hint bubbles (`sanitize_hint_text` enforces this).
- Leak Class 12 calculus into Class 9 student dashboards.