# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git Workflow

After completing any meaningful unit of work, commit the changes and push to GitHub. Do this regularly — after each feature, fix, or logical change — so work is never lost.

```bash
git add <specific-files>
git commit -m "Short, descriptive message explaining what and why"
git push origin master
```

Commit messages should be concise and describe the change (e.g. `add shield power-up to shooter`, `fix speeder zigzag going out of bounds`). Never bundle unrelated changes into one commit.

## Running the Games

These are standalone HTML files with no build step, dependencies, or server required. Open directly in a browser:

- `shooter.html` — Retro top-down arcade shooter
- `tictactoe.html` — Two-player Tic Tac Toe

## Architecture

Both games are self-contained single-file HTML documents with inline CSS and JavaScript. There is no module system, bundler, or external dependencies.

### shooter.html

A canvas-based game (800×600) using a fixed game loop driven by `requestAnimationFrame`.

**Core architecture:**
- **State machine** — `STATES` enum (`MENU`, `PLAYING`, `LEVEL_COMPLETE`, `GAME_OVER`, `PAUSED`, `HOW_TO_PLAY`) controls which screen is rendered each frame
- **Game loop** — `gameLoop(timestamp)` computes `dt` (delta time in seconds, capped at 0.05s) and dispatches update+draw per state
- **Entity classes** — `Player`, `Bullet`, `Enemy` (base), `CrawlerEnemy`, `TankEnemy`, `SpeederEnemy`, `ShooterEnemy` — all hold their own state and expose `update(dt)` / `draw()` methods
- **Wave/level manager** — `LEVEL_DATA` array defines 5 levels with wave compositions; `updateWaveManager(dt)` handles spawn queues, wave progression, and level completion transitions
- **Collision** — `checkCollisions()` runs circle-circle detection between bullets↔enemies and bullets/enemies↔player each frame
- **Obstacles** — Static rect definitions in `OBSTACLE_DEFS`; `resolveObstacleCollision()` pushes entities out using minimum overlap axis
- **Input** — Global `keys` object (keyboard) and `mouse` object updated via event listeners; `clickConsumed` flag prevents multi-button clicks in one frame

**Score values:** Crawler=10, Speeder=20, ShooterEnemy=25, Tank=30

### tictactoe.html

Simple DOM-based game. State is a 9-element array (`board`). Win detection checks all 8 combinations in `WINS`. Score persists across restarts within the same session.

---

## Skills System

Claude skills live in `.claude/skills/`. Each skill has a `SKILL.md` (intent + usage) and a `scripts/` folder (execution scripts). Skills **auto-activate** based on what you ask — no explicit invocation needed.

**Workflow:** Write → Code Review (subagent) → QA (subagent) → Fix → Ship

**Self-annealing loop:** When a skill fails → diagnose → fix → update `SKILL.md` → system improves over time.

**Operating principles:**
- Claude makes decisions; deterministic scripts execute
- All API keys via environment variables, never hardcoded
- Cloud deliverables stay in cloud services; intermediates go in `.tmp/` (gitignored)

### Available Skills

| Skill | Description |
|-------|-------------|
| `product-council` | Convene 4 AIs (Claude, GPT-4o, Gemini, Perplexity) to deliberate and reach consensus on research, PRDs, competitive analysis, transcripts, and recommendations |
| `add-webhook` | Add new Modal webhooks for event-driven execution |
| `casualize-names` | Convert formal names to casual versions for cold email personalization |
| `classify-leads` | Classify leads using LLM for complex distinctions (SaaS vs agency, etc.) |
| `create-proposal` | Generate PandaDoc proposals from client info or sales call transcripts |
| `cross-niche-outliers` | Find viral YouTube videos from adjacent niches for content patterns |
| `design-website` | Generate a premium mockup website for a prospect (buildinamsterdam style) |
| `generate-report` | Generate weekly weather reports for Canada using Open-Meteo API + PDF |
| `gmail-inbox` | Manage emails across multiple Gmail accounts with unified tooling |
| `gmail-label` | Auto-label Gmail emails into Action Required / Waiting On / Reference |
| `gmaps-leads` | Scrape Google Maps for B2B leads with website enrichment and contact extraction |
| `instantly-autoreply` | Auto-generate intelligent replies to Instantly email threads via knowledge bases |
| `instantly-campaigns` | Create cold email campaigns in Instantly with A/B testing |
| `literature-research` | Search academic literature and perform deep research reviews |
| `local-server` | Run Claude orchestrator locally with Cloudflare tunneling |
| `modal-deploy` | Deploy execution scripts to Modal cloud |
| `onboarding-kickoff` | Automated client onboarding post-kickoff: leads + campaigns + auto-reply |
| `pan-3d-transition` | Create 3D pan/swivel transition effects for videos using Remotion |
| `recreate-thumbnails` | Face-swap YouTube thumbnails to feature a specified person using AI |
| `scrape-leads` | Scrape/verify business leads via Apify, classify with LLM, enrich emails, save to Sheets |
| `skool-monitor` | Monitor and interact with Skool communities (read, post, reply, like, search) |
| `skool-rag` | Query Skool community content using RAG pipeline with vector search |
| `title-variants` | Generate title variants for YouTube videos from outlier analysis |
| `upwork-apply` | Scrape Upwork jobs and generate personalized proposals with cover letters |
| `video-edit` | Edit talking-head videos: remove silences with neural VAD, add 3D swivel transitions |
| `welcome-email` | Send welcome email sequence to new clients |
| `youtube-outliers` | Find viral YouTube videos in a niche for competitive intelligence |

### ProductCouncil (Primary AI Assistant)

The `product-council` skill is the main ProductAssistant for all analytical and product work. It convenes Claude, GPT-4o, Gemini, and Perplexity in a structured deliberation — each AI challenges the others until ≥80/100 consensus is reached.

**Supported tasks:** research Q&A · transcript/document analysis · PRD generation · competitive analysis · strategic recommendations

**Anti-hallucination:** Perplexity provides real-time web citations; all AIs declare confidence levels; disputed claims are marked `[DISPUTED:]` in output.

**Output:** `./output/council/[timestamp]-[task].md` + PDF

**Run it:**
```bash
# Research
python3 .claude/skills/product-council/scripts/council.py research \
  --query "Your question here"

# Analyze a transcript
python3 .claude/skills/product-council/scripts/council.py analyze \
  --file ./transcript.txt --query "Key decisions and action items?"

# PRD, competitive analysis, or recommendations
python3 .claude/skills/product-council/scripts/council.py prd --query "..."
python3 .claude/skills/product-council/scripts/council.py competitive --query "..."
python3 .claude/skills/product-council/scripts/council.py recommend --query "..."
```

**Required:** `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY` in `.env`
**Install:** `pip3 install anthropic openai google-generativeai python-dotenv reportlab`

### Subagents

Subagents live in `.claude/agents/` and can be invoked in parallel for quality gates:

| Agent | Purpose |
|-------|---------|
| `code-reviewer` | Unbiased code review — returns PASS/FAIL with issues by severity (high/medium/low) |
| `research` | Deep web + file research — returns answer, key findings with sources, details |
| `qa` | Generates and runs tests (happy path, edge cases, error cases), reports results |
| `email-classifier` | Categorizes emails into Action Required / Waiting On / Reference |

---

## Website Design Principles

All websites in this repo follow the **single-file HTML** architecture: inline CSS, inline JS, zero build step, no npm dependencies. Open directly in a browser.

### Design System (see `design-reference/` for full reference)

**Dark theme defaults:**
- Background: `#000000` or `#0e0f11`; Cards: `#0a0a0a` / `#141617`
- Accent options: Emerald `#10b981`, Yellow `#eef35f`, Purple `#7b66ff`
- Font: **Inter** (Google Fonts CDN), weights 300–800, letter-spacing `-0.03em`
- Corner radii: 4px (small), 6px (medium), 8px (large) — no rounded pills

**Standard page structure:**
1. Hero (headline + subtitle + CTA)
2. Social proof (logo ticker or client logos)
3. Case studies / results cards with real stats
4. How It Works (3-step process)
5. Services grid (6 cards)
6. Final CTA section
7. Footer

**Standard interactive features:**
- Scroll-triggered reveal animations (Intersection Observer + CSS transitions)
- Animated counters with easeOutQuart easing
- Mouse-following cursor glow effect (desktop only)
- Scroll progress indicator
- Card hover lift (`translateY(-4px)` + shadow)

**Reference files:**
- `design-reference/general-example.html` — full dark-theme example with yellow accent
- `design-reference/design-system.md` — complete patterns, color tables, JS/CSS snippets
