/** @type {import('tailwindcss').Config} */

/**
 * AURA "Japandi" theme palette (Japanese minimalism + Scandinavian warmth).
 *
 * Material story: washi rice paper, sumi ink, hinoki cedar, matcha moss, raw clay.
 * The palette is LIGHT-first: the neutral ramp runs from ink (50) to paper (950), the
 * inverse of the retired dark "warm ember" ramp. That inversion means an existing
 * `bg-sand-950` page shell now renders as rice paper and `text-sand-100` renders as ink
 * without rewriting call sites.
 *
 * Role mapping used across the app (token names kept from the previous theme):
 *   sand  -> warm neutral (paper, ink, hairline borders) - replaces slate
 *   ember -> primary accent (Physics, primary CTAs) - hinoki cedar / muted terracotta
 *   olive -> secondary accent (Biology) - matcha moss
 *   clay  -> tertiary accent (Mathematics, telemetry, hints) - raw clay / dusty brick
 *   amber -> Tailwind default, kept for warnings, ratings and gradient mid-tones
 *
 * Contrast contract (validated against the page paper `#EAE4D8`):
 *   *-400 is the accent tint for text/icons on paper (>= 4.6:1)
 *   *-600 is the solid button fill and pairs with white text (>= 5:1)
 *   *-500/10 + *-500/20 stay the soft badge washes (opacity tints over paper)
 *   *-800..950 are the pale washes used by gradients and overlay scrims
 */
const japandiPalette = {
  sand: {
    50: '#1E1B18', // sumi ink — highest-contrast text
    100: '#2B2723', // ink — primary body text
    200: '#3D3833', // graphite — emphasised body text
    300: '#4A443C', // stone — secondary text
    400: '#5F584D', // weathered stone — supporting copy
    500: '#6C6458', // muted clay-gray — metadata / labels
    600: '#A9A196', // pale stone — scrollbar hover
    700: '#C2B9AB', // hairline (strong) — scrollbar rails
    800: '#D9D1C3', // hairline — panel + card borders
    850: '#E2DBCE', // hairline (subtle)
    900: '#F4EFE6', // washi paper — panels, cards
    950: '#EAE4D8', // rice paper — page background
  },
  ember: {
    50: '#331807',
    100: '#45220E',
    200: '#582D14',
    300: '#6E3A1D',
    400: '#8A4B2A', // cedar text tint on paper
    500: '#A5623A', // tints, borders, focus ring
    600: '#9A5530', // solid fill (white text)
    700: '#7E4325',
    800: '#B27A50',
    850: '#C08C63',
    900: '#D3A582',
    950: '#EBD3BE', // palest cedar wash
  },
  olive: {
    50: '#1D2A0F',
    100: '#283817',
    200: '#33481F',
    300: '#3F5A2B',
    400: '#4A6530', // matcha text tint on paper
    500: '#5E7A3E',
    600: '#556E38', // solid fill (white text)
    700: '#3E5528',
    800: '#86A163',
    850: '#97AE77',
    900: '#B6C79C',
    950: '#DDE6CB', // palest moss wash
  },
  clay: {
    50: '#421A19',
    100: '#5A2624',
    200: '#6E312E',
    300: '#853E3A',
    400: '#9A4A46', // clay text tint on paper
    500: '#A85B56',
    600: '#9C524D', // solid fill (white text)
    700: '#83403C',
    800: '#C58A85',
    850: '#CF9A95',
    900: '#DDB6B2',
    950: '#EFD9D6', // palest clay wash
  },
};
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  // ChapterNav builds its accent class dynamically (`text-${activeColor}-400`), so the
  // subject accent classes must be safelisted to guarantee they land in the bundle.
  safelist: [
    'text-ember-400',
    'text-olive-400',
    'text-clay-400',
  ],
  theme: {
    extend: {
      colors: japandiPalette,
      // Warm default focus ring (Tailwind ships a blue-500 default in preflight).
      ringColor: {
        DEFAULT: japandiPalette.ember[500],
      },
      // Japandi depth: soft, wide, low-opacity ink shadows instead of coloured glow.
      boxShadow: {
        'japandi-sm': '0 2px 8px -4px rgba(43, 39, 35, 0.16)',
        japandi: '0 12px 32px -20px rgba(43, 39, 35, 0.26)',
        'japandi-lg': '0 28px 64px -36px rgba(43, 39, 35, 0.32)',
      },
    },
  },
  plugins: [],
}
