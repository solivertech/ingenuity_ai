# IngenuityAI — Brand Package

This folder contains all brand assets and design tokens for the IngenuityAI product.
Claude Code should reference these files when building any UI component, page, or feature.

## Files

```
ingenuityai-brand/
├── brand-style-guide.html     # Full visual style guide — open in browser
├── assets/
│   ├── brand-tokens.json      # All design decisions as structured JSON
│   └── brand.css              # CSS variables + utility classes — import globally
├── icons/
│   ├── icon-mark.svg          # Standalone rotor mark (no background)
│   └── app-icon-512.svg       # Contained app icon (rounded square, 512px)
└── logos/
    ├── wordmark-light.svg     # Horizontal lockup for light backgrounds
    └── wordmark-dark.svg      # Horizontal lockup for dark backgrounds
```

## Quick reference

### Colors

| Token              | Hex       | Use                          |
|--------------------|-----------|------------------------------|
| `--brand-dark`     | #063D2E   | Primary dark, icon bg, navbar |
| `--brand-primary`  | #0F8F6E   | Buttons, links, focus rings  |
| `--brand-accent`   | #1DB88E   | "AI" suffix, active states   |
| `--brand-wash`     | #E1F5EE   | Tag backgrounds, info fills  |
| `--ink`            | #111110   | Primary body text            |
| `--slate`          | #444441   | Secondary text               |
| `--muted`          | #888780   | Labels, placeholders         |
| `--stone`          | #F1EFE8   | Surface backgrounds          |

### Typography

- Font: `-apple-system, 'Helvetica Neue', Arial, sans-serif` (system stack, no web font needed)
- Mono: `'SF Mono', 'Fira Code', 'Consolas', monospace`
- Display (hero): 52px / weight 300 / tracking -1.5px
- H1: 32px / weight 400 / tracking -0.5px
- H2: 22px / weight 500
- H3: 17px / weight 500
- Body: 15px / weight 400 / line-height 1.6
- Labels: 11px / weight 500 / tracking 0.08em / uppercase

### Wordmark rules

- "Ingenuity" — weight 300, dark (#111110 on light, #ffffff on dark)
- "AI" — weight 600, always teal (#0F8F6E on light, #1DB88E on dark)
- Minimum width: 120px
- Never use on colored or photographic backgrounds without a solid container

### Logo file usage

| Context                    | File                        |
|----------------------------|-----------------------------|
| Navbar / header (light bg) | `logos/wordmark-light.svg`  |
| Navbar / header (dark bg)  | `logos/wordmark-dark.svg`   |
| App icon / favicon         | `icons/app-icon-512.svg`    |
| Standalone mark            | `icons/icon-mark.svg`       |

### Buttons

```css
/* Primary */
background: #063D2E; color: #E1F5EE;

/* Outline */
background: transparent; color: #0F8F6E; border: 1.5px solid #0F8F6E;

/* Ghost */
background: #F1EFE8; color: #444441; border: 0.5px solid #D3D1C7;
```

### Status pills

```css
/* Active */  background: #E1F5EE; color: #085041;
/* Paused */  background: #FAEEDA; color: #633806;
/* Error */   background: #FCEBEB; color: #791F1F;
/* Neutral */ background: #F1EFE8; color: #444441;
```

### Spacing scale

4px · 8px · 16px · 24px · 48px · 80px

### Border radius

4px (subtle) · 8px (default) · 12px (cards) · 16px (large) · 9999px (pills)

## Implementation notes

1. Import `assets/brand.css` as the first stylesheet in your global CSS.
2. Reference `assets/brand-tokens.json` for any programmatic access to tokens (e.g. Tailwind config, Storybook theme, React theme context).
3. Use SVG files directly — they are self-contained and scale to any size.
4. The icon uses a 512x512 viewBox internally — scale with width/height attributes, not CSS transforms.
5. All colors are hardcoded hex — no dependency on any design system library.
