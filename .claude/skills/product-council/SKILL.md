---
name: product-council
description: >
  Convene a council of 4 AI agents (Claude, GPT-4o, Gemini, Perplexity) that
  deliberate, challenge each other, and reach consensus before producing output.
  Use when the user asks to research a topic, analyze a transcript or document,
  create a PRD, run a competitive analysis, or get strategic recommendations.
  The council requires consensus (≥80/100) before delivering a final answer.
  Produces a markdown report + PDF with the full deliberation transcript.
allowed-tools: Bash, Read, Write
---

# ProductCouncil — AI Deliberation System

## Goal

Run a multi-round deliberation across 4 AI council members that challenge each
other's claims, require sources for factual assertions, and only produce output
when ≥80% consensus is reached. All tasks are delivered as structured markdown
documents and optional PDFs.

## Council Members

| Name | Role | Strength |
|------|------|---------|
| Claude | Analyst | Structured reasoning, frameworks, assumptions |
| GPT-4o | Strategist | Business impact, market dynamics, trade-offs |
| Gemini | Researcher | Cross-domain synthesis, analogy, hypothesis testing |
| Perplexity | Fact-Checker | Real-time web sources, citation grounding |

## Deliberation Protocol

1. **Round 1** — All 4 AIs answer independently and in parallel
2. **Consensus Check** — Claude scores agreement 0–100; if ≥80 → synthesize and done
3. **Round 2** — Each AI critiques others' responses and proposes synthesis
4. **Consensus Check** — If ≥80 → synthesize and done
5. **Round 3** — Each AI writes a final consensus answer
6. **Final output** — Delivered with any `[DISPUTED:]` markers if consensus < 80

## Task Types

| Command | Description |
|---------|-------------|
| `research` | Research Q&A with citations and source verification |
| `analyze` | Analyze a text file, transcript, or document |
| `prd` | Generate a Product Requirements Document |
| `competitive` | Competitive analysis across multiple products |
| `recommend` | Strategic recommendation with pros/cons and rationale |

## Scripts

- `./scripts/council.py` — Main CLI entry point
- `./scripts/deliberate.py` — Deliberation engine
- `./scripts/ai_clients.py` — Async API wrappers for all 4 AIs
- `./scripts/output.py` — Markdown + PDF document generation
- `./scripts/prompts.py` — Personas, task prompts, round templates

## Dependencies

```bash
pip3 install anthropic openai google-generativeai python-dotenv reportlab
```

## Environment Variables

Set these in `.env` at the project root:

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GEMINI_API_KEY=...
PERPLEXITY_API_KEY=...
```

The council works with as few as 2 keys — missing members are skipped with a warning.

## Usage

### Research Query
```bash
python3 .claude/skills/product-council/scripts/council.py research \
  --query "What are the key trends in AI product management in 2025?"
```

### Analyze a Transcript
```bash
python3 .claude/skills/product-council/scripts/council.py analyze \
  --file ./transcript.txt \
  --query "What are the key decisions and open questions?"
```

### Generate a PRD
```bash
python3 .claude/skills/product-council/scripts/council.py prd \
  --query "AI-powered meeting summarizer for enterprise Slack" \
  --context "Target users: product teams at 100–500 person companies"
```

### Competitive Analysis (no PDF)
```bash
python3 .claude/skills/product-council/scripts/council.py competitive \
  --query "Notion vs Linear vs Coda for product teams" \
  --no-pdf
```

### Strategic Recommendation
```bash
python3 .claude/skills/product-council/scripts/council.py recommend \
  --query "Should we build vs buy our analytics infrastructure?" \
  --context "20-person B2B SaaS, $2M ARR, 3 engineers, $5k/mo budget"
```

### Flags
| Flag | Default | Description |
|------|---------|-------------|
| `--query / -q` | required | The main question or instruction |
| `--context / -c` | "" | Additional background context |
| `--file / -f` | none | File to analyze (analyze task only) |
| `--output-dir` | ./output/council | Where to save reports |
| `--max-rounds` | 3 | Max deliberation rounds (1–3) |
| `--no-pdf` | false | Skip PDF generation |
| `--quiet` | false | Suppress round-by-round console output |

## Output

- `./output/council/[YYYYMMDD-HHMMSS]-[task-type].md` — Full deliberation report
- `./output/council/[YYYYMMDD-HHMMSS]-[task-type].pdf` — Styled PDF version

## Anti-Hallucination Design

1. **Perplexity** has real-time web access and cites `[Source: URL]` for every claim
2. All AIs append `CONFIDENCE: HIGH/MEDIUM/LOW` to Round 1 responses
3. Round 2 Critique phase — Perplexity flags `UNVERIFIED:` claims from other AIs
4. Consensus filter — unsourced claims challenged by others lower the consensus score
5. `[DISPUTED:]` markers in final output for anything not fully agreed upon
