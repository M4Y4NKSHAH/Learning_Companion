# 🎨 Design — Learning Companion (AURA)

> Visual & interaction design reference for the frontend. Covers the Landing Page and the
> Glass-Box Dashboard, the design tokens, animations, and component inventory.

---

## 1. Design Overview

Two distinct surfaces share one visual language:

| Surface | File | Mood |
| --- | --- | --- |
| **Landing Page** | `src/components/LandingPage.jsx` | Marketing: hero, feature grid, offering cards, gallery lightbox |
| **Glass-Box Dashboard** | `src/App.jsx` | Telemetry: study deck, practice lab, exam, live "active node" readout |

Both use the **japandi / washi-paper** aesthetic: light rice-paper background, sumi-ink
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
| `sand` | Neutrals — paper, ink, hairline borders, body copy (replaced `slate`) | `sand-950 #EAE4D8` (paper) → `sand-50 #1E1B18` (sumi ink) |
| `ember` | Primary accent — Physics, primary CTAs, brand gradients (replaced `blue`) | `ember-500 #A5623A`, `ember-600 #9A5530` (hinoki cedar) |
| `olive` | Secondary accent — Biology, success/mastery states (replaced `emerald`) | `olive-500 #5E7A3E`, `olive-600 #556E38` (matcha moss) |
| `clay` | Tertiary accent — Mathematics, brand gradients, hints & alerts (replaced `purple` + `rose`) | `clay-500 #A85B56`, `clay-600 #9C524D` (raw clay) |
| `amber` / `yellow` | Tailwind defaults kept for warnings, ratings and gradient mid-tones (absorbed the old `indigo`/`cyan`/`teal`) | — |

Every scale defines `50–950` plus `850` (used by `border-sand-850`). The neutral ramp is
**inverted relative to a dark theme**: `sand-50` is the darkest (ink) and `sand-950` the
lightest (paper), so `bg-sand-950` + `text-sand-100` still mean "page surface + body ink".
Usage pattern: `*-600` fills pair with white text (≥ 5:1), `*-400` is the text/icon tint on
paper (≥ 4.8:1), `*-500/10` + `*-500/20` are the soft badges, and `*-800…950` are the pale
gradient/overlay washes.

### Subject → Accent color map (`getSubjectColor` in App.jsx)

| Subject | Accent |
| --- | --- |
| Physics | Ember (`text-ember-400`, `bg-ember-500/10`, `border-ember-500/20`) |
| Biology | Olive (`text-olive-400`, `bg-olive-500/10`, `border-olive-500/20`) |
| Mathematics | Clay (`text-clay-400`, `bg-clay-500/10`, `border-clay-500/20`) |

The lowercase family name is also handed to child views as the `activeColor` prop
(`'ember' | 'olive' | 'clay'`, see `App.jsx` → `ChapterNav`/`TheoryExplorer`). Because
`ChapterNav` composes `text-${activeColor}-400` dynamically, those three classes are
safelisted in `tailwind.config.js`.

---

## 3. Landing Page Anatomy (`LandingPage.jsx`)

Sections, top to bottom:

1. **Sticky header** — AURA logo (gradient ember→clay icon), desktop nav anchors
   (Features, Gallery, etc.), mobile hamburger menu.
2. **Hero** — headline with animated gradient text, CTA (`Start Learning`), floating
   blurred orbs (`animate-float` / `animate-float-slow`) and the hero image, rendered as a
   warm printed plate (`.japandi-plate`).
3. **Features** — feature cards with lucide icons (RAG study decks, Socratic feedback,
   glass-box cognitive routing…).
4. **Offerings — "2×3 grid"** — three **subject cards** (Physics `Atom`, Biology `Dna`,
   Mathematics `Binary`) + three **level cards** (Class 10 `School`, Class 11-12
   `Library`, Undergraduate `GraduationCap`).
5. **Selection modal** — pick subject + level → "Launch Dashboard". Error text shows if
   both aren't chosen. Cards animate with shimmer / glow-pulse.
6. **Gallery lightbox** — 5 preview images (`heroImage.png`, `gallery1–5.png`); prev/next
   arrows, counter, escape-to-close, body scroll lock.
7. **Footer** — social icons (Instagram, Facebook, Twitter) + nav.

### Interaction details
- `confirmSelection()` requires **both** subject and tier, then calls
  `onStartLearning(subject, tier)` (prop from `App.jsx`).
- Gallery keyboard support: `←` `→` `Esc` (see the `useEffect` in LandingPage).
- Mobile menu + modal both use `useState` toggles; modal announced via `modalError`.
- Scroll-to-section uses `scrollIntoView({behavior:'smooth'})` + `Reveal.jsx` for
  scroll-triggered entrance animations.

---

## 4. Dashboard Anatomy (`App.jsx`)

Left rail → central panel → right telemetry:

- **Header** — subject color accent, tier switcher pills (`Class 10 / Class 11-12 /
  Undergraduate`), subject switcher, chat toggle.
- **Left nav — Workspace Modes:** Study Deck (`theory`), Practice Lab (`quiz`),
  Threshold Exam (`final_exam`). Disabled when no content for the tier.
- **Context Metadata panel** — subject, tier, active node, fuzzy telemetry
  (score / degree of failure / performance tier, grayed out or pulsing).
- **Central views:**
  - *Study Deck:* 3D **flip cards** (`.flip-card`), prev/next card, "Generate AI
    Flashcards" button (calls `/api/tutor/generate-flashcards`).
  - *Practice Lab:* question text + free-answer input; submits to
    `/api/tutor/evaluate-short-answer` → sanitized hint + fuzzy grade shown inline.
  - *Threshold Exam:* timed questions, per-question timer, submit → `/api/tutor/evaluate-exam`
    report (score, tier, remediation plan, growth metrics).
  - *Chat pane:* conversation log + type-ahead; each tutor message shows
    `active_node` + `depth_level` badge = the **glass-box telemetry**.
- **On-demand hint launcher** button in exam view (`showSideHintBox`).

### Dashboard component states
- `loading` overlay/spinner, `isGeneratingCards` spinner, `isFlipped` flip state,
  `examReport` full-report view, per-question `lastQuestionEvaluated` feedback.
- Empty states when `cards/quizzes/finalExams` are empty (buttons disabled).

### Auth-gated view state machine
`App.jsx` uses a `view` state (`'landing' | 'auth' | 'dashboard'`) backed by
`src/lib/auth.js`:

- **Initial load:** if a valid `aura_session` cookie exists → `dashboard`;
  otherwise → `landing`.
- **Landing → Auth:** any CTA (`Get Started`, `Start Learning`, subject cards)
  calls `setView('auth')`.
- **Auth → Dashboard:** `AuthPage.onAuthenticated(session)` writes the session
  cookie and calls `setView('dashboard')`.
- **Dashboard guard:** a `useEffect` watches `view === 'dashboard'` and bounces
  to `landing` if `isAuthenticated()` returns false (cookie expired/tampered).
- **Sign out:** `handleSignOut()` clears the session cookie + returns to landing.

**Do / Don't:** see §9 — don't expose raw password hashes to the UI (the
`Aura Auth Page` dev-account list already strips salts/hashes via
`listLocalAccounts()`).
---

## 5. Animation & Motion Inventory (`src/index.css`)

| Utility | Effect | Applied to |
| --- | --- | --- |
| `.animate-fadeIn` | 0.4s opacity fade | Modal + lightbox overlays |
| `.animate-float` / `-slow` | 8s / 12s vertical+horizontal drift | Hero orbs |
| `.animate-gradient-text` | 6s hue-shifting gradient | Hero headline |
| `.animate-glow-pulse` | 4s opacity pulse on cards | Offering cards |
| `.animate-shimmer` | 3.5s diagonal ink sheen sweep (`::before`) | Feature cards |
| `.animate-spin-slow` | 14s linear spin ring | Hero visual |
| `.animate-breathe` | 3s gentle scale | Hero icon |
| `.pulse-active` | 2s expanding pulse-ring | Active telemetry indicator |
| `.flip-card*` | 0.6s `rotateY(180deg)` cubic-bezier | Flashcards |
| `.custom-scrollbar` | 6px warm paper rails (`sand-950` / `sand-700`) | Log / RAG streams |
| `.mask-fading-edge` | Vertical fade mask | Streaming text frames |
| `.japandi-plate` | Invert + `saturate(.42)` + `sepia(.14)` treatment for the legacy dark screenshots | Hero + gallery art |

**Accessibility:** `prefers-reduced-motion: reduce` disables every animation listed above.

---

## 6. Micro-copy & Tone

- Brand name: **AURA** (sumi-ink→stone gradient logotype with `BrainCircuit` brain icon).
- CTA verbs: *Launch Dashboard*, *Start Learning*, *Explore Course*.
- Academic framing: "Foundational concepts" → "Advanced high-school curriculum" →
  "Rigorous academic content tailored for university students".
- Chat/telemetry labels are engineer-styled (mono uppercase: `WORKSPACE MODES`,
  `CONTEXT METADATA`, `ACTIVE ROUTING NODE`) — reinforcing the "glass box" concept.

---

## 7. Component Inventory

| Component | File | Purpose |
| --- | --- | --- |
| `LandingPage` | `components/LandingPage.jsx` | Marketing + onboarding flow |
| `AuthPage` | `components/AuthPage.jsx` | Local-cookie sign-in / sign-up gate |
| `Reveal` | `components/Reveal.jsx` | Scroll-triggered entrance wrapper |
| `App` | `App.jsx` | Dashboard shell + all workspace views |
| `HintMarkdown` | `App.jsx` (internal) | Renders `##`, `**bold**`, bullets/numbers from tutor hints |
| `formatInlineMarkdown` | `App.jsx` (internal) | Bold/`<strong>` tokenizer for hint text |

### Iconography
- All icons come from **`lucide-react`** (`BrainCircuit`, `GraduationCap`, `School`,
  `Library`, `Atom`, `Dna`, `Binary`, `ChevronRight/Left`, `Menu`, `X`, `Check`, …).
- Subjects use single lucide glyphs as brand marks.

---

## 8. Responsive Behavior

- Landing nav collapses to hamburger menu below `md`.
- Offerings grid fills width on mobile; gallery lightbox caps at `max-w-[90vw] max-h-[85vh]`.
- Dashboard layout is `12-col` on `lg+`, stacks single-column on small screens.
- Recent commit `35d441ad` "Fixed responsiveness on small screens" is the reference
  pass for small-viewport fixes.

---

## 9. Do / Don't Reference

**Do:** keep the `sand-950` rice-paper base + washi `glass-panel` cards; use the subject accent
map (`ember` / `olive` / `clay`); keep every accent muted and natural — `sand` ink/paper for
neutrals, `ember` for primary CTAs, `olive` for success, `clay` for hints/alerts, Tailwind
`amber-800`/`yellow-800` for warnings on paper; use `text-sand-200`→`text-sand-50` for headings
and body ink; prefer `shadow-japandi*` (or bare `shadow-sand-300/25`) for depth; add
`prefers-reduced-motion` guards; prefer small-hint text `text-[10px]`/`text-xs` for metadata;
use mono uppercase for telemetry labels.

**Don't:** introduce new fonts (Outfit only is loaded); re-introduce cool or neon families
(`slate`, `blue`, `emerald`, `purple`, `indigo`, `cyan`, `teal`, `rose` are no longer part of
the palette); put light text on paper — `text-white` is only valid on `*-600` accent fills,
everything else uses `text-sand-50`…`text-sand-500`; use translucent white hairlines
(`border-white/20` → `border-sand-800`); use near-black panels for overlays (scrims are
`bg-sand-50/65`…`/85` ink, cards stay washi); add background images (the palette is flat +
gradient-wash based); bypass the `activeColor` map when adding subject-tinted UI.