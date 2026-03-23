# Website Design System Reference

Distilled from two production websites: LeftClick agency site and the Website Design General template.
Use these principles when designing or critiquing any website in this repo.

---

## Core Philosophy

- Single-file HTML — inline CSS and JS, zero build step, no npm dependencies
- Dark theme as default (lighter variants possible); high-contrast accent colors
- Desktop AND mobile responsive from the start
- No rounded pills — squared/luxe aesthetic (`border-radius: 4–8px` max)

---

## Color Systems

### Dark Agency Style (LeftClick)
| Role | Hex |
|------|-----|
| Background | `#000000` |
| Cards/sections | `#0a0a0a`, `#111111` |
| Accent primary | `#10b981` (emerald) |
| Accent hover | `#34d399` |
| Accent active | `#059669` |
| Text primary | `#ffffff` |
| Text secondary | `#a1a1aa` |

### Dark Tech Style (Website Design General)
| Role | Hex |
|------|-----|
| Background | `#0e0f11` |
| Sections | `#141617` |
| Accent primary | `#eef35f` (yellow/lime) |
| Accent purple | `#7b66ff` |
| Accent teal | `#00cbaa` |
| Text secondary | `#a1a1aa` |

---

## Typography

- **Font**: Inter (Google Fonts CDN) — `Inter Tight` variant for headings
- **Weights**: 300 (light body) → 800 (hero headlines)
- **Letter spacing**: `-0.03em` on headings for tight, luxury feel
- Load via: `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">`

---

## Page Structure (Standard Marketing Site)

1. **Hero** — Headline + subtitle + CTA buttons (+ floating icons or gradient orbs)
2. **Social Proof** — Scrolling logo ticker or client logos
3. **Case Studies / Results** — 2–3 cards with real stats
4. **How It Works** — 3-step numbered process
5. **Services** — 6-card grid
6. **CTA Section** — Final call-to-action with Calendly or contact link
7. **Footer** — Logo, nav links, copyright

---

## Interactive Features (Standard Set)

```js
// 1. Scroll-triggered reveal — add class 'reveal' to elements, trigger on scroll
const observer = new IntersectionObserver(entries => {
  entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
}, { threshold: 0.1 });
document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

// 2. Animated counters — easeOutQuart easing
function animateCounter(el, target, duration = 2000) {
  let start = 0, startTime = null;
  const step = ts => {
    if (!startTime) startTime = ts;
    const progress = Math.min((ts - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 4); // easeOutQuart
    el.textContent = Math.floor(eased * target).toLocaleString();
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// 3. Mouse-following cursor glow (desktop only)
document.addEventListener('mousemove', e => {
  document.documentElement.style.setProperty('--cursor-x', e.clientX + 'px');
  document.documentElement.style.setProperty('--cursor-y', e.clientY + 'px');
});
// CSS: .glow { background: radial-gradient(circle at var(--cursor-x) var(--cursor-y), rgba(16,185,129,0.15), transparent 50%); }

// 4. Scroll progress indicator
window.addEventListener('scroll', () => {
  const pct = window.scrollY / (document.body.scrollHeight - window.innerHeight) * 100;
  document.querySelector('.scroll-progress').style.width = pct + '%';
});
```

---

## CSS Patterns

```css
/* Nav with backdrop blur */
nav { position: fixed; top: 0; width: 100%; backdrop-filter: blur(12px); z-index: 100; }

/* Card hover lift */
.card { transition: transform 0.2s, box-shadow 0.2s; }
.card:hover { transform: translateY(-4px); box-shadow: 0 12px 40px rgba(0,0,0,0.4); }

/* Reveal animation */
.reveal { opacity: 0; transform: translateY(24px); transition: opacity 0.6s, transform 0.6s; }
.reveal.visible { opacity: 1; transform: none; }

/* Scrolling logo ticker */
@keyframes ticker { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.ticker-track { display: flex; animation: ticker 20s linear infinite; }
```

---

## Reference Files

- `design-reference/general-example.html` — Full dark-theme site with yellow accent (Tailwind CSS + Inter Tight)
- LeftClick live: https://leftclick-agency.netlify.app (emerald green accent, pure black background)
