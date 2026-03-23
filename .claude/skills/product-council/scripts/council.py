#!/usr/bin/env python3
"""
ProductCouncil — CLI Entry Point

Convene a council of 4 AIs (Claude, GPT-4o, Gemini, Perplexity) to deliberate
on product tasks. Produces a markdown + PDF report with the full reasoning chain.

Usage:
    python3 council.py research --query "..."
    python3 council.py analyze --file transcript.txt --query "Key decisions?"
    python3 council.py prd --query "AI meeting summarizer for Slack"
    python3 council.py competitive --query "Notion vs Linear vs Coda"
    python3 council.py recommend --query "Build vs buy analytics" --context "..."
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure scripts directory is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

from ai_clients import validate_api_keys
from deliberate import run_deliberation
from output import build_output_path, generate_markdown, generate_pdf, save_markdown
from prompts import PERSONAS


# ─────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║           P R O D U C T   C O U N C I L                     ║
╠══════════════════════════════════════════════════════════════╣
║  Council Members:                                            ║
║    Claude      —  Analyst       (Anthropic)                  ║
║    GPT-4o      —  Strategist    (OpenAI)                     ║
║    Gemini      —  Researcher    (Google)                     ║
║    Perplexity  —  Fact-Checker  (Perplexity AI)              ║
╚══════════════════════════════════════════════════════════════╝"""


# ─────────────────────────────────────────────
# CLI PARSER
# ─────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="council",
        description="ProductCouncil — Multi-AI deliberation for product tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Task Types:
  research    — Research Q&A with citations
  analyze     — Analyze a text file or transcript
  prd         — Generate a Product Requirements Document
  competitive — Competitive analysis
  recommend   — Strategic recommendations

Examples:
  python3 council.py research --query "Key AI product management trends 2025?"
  python3 council.py analyze --file transcript.txt --query "Key decisions?"
  python3 council.py prd --query "AI meeting summarizer for enterprise Slack"
  python3 council.py competitive --query "Notion vs Linear vs Coda" --no-pdf
  python3 council.py recommend --query "Build vs buy analytics" \\
      --context "20-person B2B SaaS, $2M ARR"
""",
    )

    subparsers = parser.add_subparsers(dest="task_type", metavar="TASK")

    # Common arguments shared by all subcommands
    def add_common_args(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--query", "-q", required=True, help="The question or instruction")
        sub.add_argument("--context", "-c", default="", help="Optional additional context")
        sub.add_argument(
            "--output-dir",
            default="./output/council",
            help="Output directory (default: ./output/council)",
        )
        sub.add_argument(
            "--max-rounds",
            type=int,
            default=3,
            choices=[1, 2, 3],
            help="Max deliberation rounds (default: 3)",
        )
        sub.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
        sub.add_argument(
            "--quiet", action="store_true", help="Suppress round-by-round console output"
        )

    # research
    sub_research = subparsers.add_parser("research", help="Research Q&A with citations")
    add_common_args(sub_research)

    # analyze
    sub_analyze = subparsers.add_parser("analyze", help="Analyze a text file or transcript")
    add_common_args(sub_analyze)
    sub_analyze.add_argument(
        "--file", "-f", default=None, help="Path to file to analyze (loaded as context)"
    )
    # make --query optional for analyze (can be inferred from file)
    sub_analyze.add_argument_group()

    # prd
    sub_prd = subparsers.add_parser("prd", help="Generate a Product Requirements Document")
    add_common_args(sub_prd)

    # competitive
    sub_comp = subparsers.add_parser("competitive", help="Competitive analysis")
    add_common_args(sub_comp)

    # recommend
    sub_rec = subparsers.add_parser("recommend", help="Strategic recommendations")
    add_common_args(sub_rec)

    return parser


# ─────────────────────────────────────────────
# MAIN ASYNC RUNNER
# ─────────────────────────────────────────────

async def run(args: argparse.Namespace) -> int:
    """Main async execution. Returns exit code."""

    # ── 1. Print banner ──
    if not args.quiet:
        print(BANNER)
        print(f"\n  Task:       {args.task_type.upper()}")
        print(f"  Max Rounds: {args.max_rounds}")
        print(f"  Threshold:  80/100")

    # ── 2. Validate API keys ──
    present, missing = validate_api_keys()
    if missing:
        print(f"\n  ⚠  Missing API keys: {', '.join(missing)}")
        print("     Add them to .env — those council members will be absent.")
    if len(present) < 2:
        print(
            "\n  ✗  Council requires at least 2 active members.\n"
            "     Please set at least 2 API keys in .env and retry."
        )
        return 1

    if not args.quiet:
        active_names = [PERSONAS[k]["name"] for k in present]
        print(f"\n  Active council: {', '.join(active_names)}\n")

    # ── 3. Load file content for 'analyze' task ──
    context = getattr(args, "context", "") or ""
    file_path = getattr(args, "file", None)

    if file_path:
        fp = Path(file_path)
        if not fp.exists():
            print(f"\n  ✗  File not found: {file_path}")
            return 1
        file_content = fp.read_text(encoding="utf-8")
        if context:
            context = f"FILE CONTENTS ({fp.name}):\n{file_content}\n\nADDITIONAL CONTEXT:\n{context}"
        else:
            context = f"FILE CONTENTS ({fp.name}):\n{file_content}"

        if not args.quiet:
            print(f"  Loaded file: {fp.name} ({len(file_content):,} chars)\n")

    # ── 4. Run deliberation ──
    if not args.quiet:
        print(f"  Query: \"{args.query}\"\n")

    session = await run_deliberation(
        task_type=args.task_type,
        query=args.query,
        context=context,
        max_rounds=args.max_rounds,
        consensus_threshold=80,
        verbose=not args.quiet,
    )

    # ── 5. Generate output ──
    if not args.quiet:
        print("  Generating output files...")

    md_path = build_output_path(args.output_dir, args.task_type, "md")
    markdown_content = generate_markdown(session)
    save_markdown(markdown_content, md_path)

    pdf_path = None
    if not args.no_pdf:
        pdf_path = build_output_path(args.output_dir, args.task_type, "pdf")
        try:
            generate_pdf(markdown_content, session, pdf_path)
        except ImportError as e:
            print(f"\n  ⚠  PDF skipped: {e}")
            pdf_path = None
        except Exception as e:
            print(f"\n  ⚠  PDF generation failed: {type(e).__name__}: {e}")
            pdf_path = None

    # ── 6. Print completion summary ──
    _print_completion(session, md_path, pdf_path)

    return 0


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _print_completion(session, md_path: Path, pdf_path) -> None:
    border = "═" * 62
    print(f"\n{border}")
    print("  OUTPUT")
    print(f"{border}")
    print(f"  Markdown : {md_path}")
    if pdf_path:
        print(f"  PDF      : {pdf_path}")
    consensus = session.final_consensus
    if consensus:
        status = "✓ CONSENSUS REACHED" if session.success else "⚠ BEST-EFFORT (no full consensus)"
        print(f"  Status   : {status} ({consensus.score}/100)")
    print(f"  Rounds   : {len(session.rounds)}")
    if session.final_answer:
        word_count = len(session.final_answer.split())
        print(f"  Answer   : {word_count} words")
    print(f"{border}\n")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.task_type:
        parser.print_help()
        sys.exit(1)

    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
