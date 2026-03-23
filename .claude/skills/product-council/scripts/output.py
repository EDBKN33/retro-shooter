#!/usr/bin/env python3
"""
ProductCouncil — Document Generation

Converts a DeliberationSession into:
  - A structured Markdown file (full deliberation transcript + final answer)
  - A styled PDF (cover page, executive summary, transcript)
"""

import textwrap
from datetime import datetime, timezone
from pathlib import Path

from deliberate import ConsensusResult, DeliberationSession
from prompts import PERSONAS

# ─────────────────────────────────────────────
# REPORTLAB IMPORTS
# ─────────────────────────────────────────────

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ─────────────────────────────────────────────
# PDF COLORS
# ─────────────────────────────────────────────

NAVY = None
ACCENT = None
CREAM_BG = None
WHITE = None
DARK_GRAY = None
MID_GRAY = None

if REPORTLAB_AVAILABLE:
    NAVY = colors.Color(0.07, 0.07, 0.18)       # #121230
    ACCENT = colors.Color(0.13, 0.55, 0.73)      # #208BBB  — teal blue
    GREEN = colors.Color(0.15, 0.65, 0.35)       # #26A659  — consensus green
    RED = colors.Color(0.80, 0.20, 0.20)         # #CC3333  — no consensus red
    CREAM_BG = colors.Color(0.97, 0.97, 0.95)    # #F7F7F2
    WHITE = colors.white
    DARK_GRAY = colors.Color(0.15, 0.15, 0.15)   # #262626
    MID_GRAY = colors.Color(0.45, 0.45, 0.45)    # #737373


# ─────────────────────────────────────────────
# PATH HELPERS
# ─────────────────────────────────────────────

def build_output_path(output_dir: str, task_type: str, extension: str) -> Path:
    """
    Build timestamped output path.
    Format: {output_dir}/{YYYYMMDD-HHMMSS}-{task_type}.{extension}
    Creates output_dir if it does not exist.
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out / f"{ts}-{task_type}.{extension}"


# ─────────────────────────────────────────────
# MARKDOWN GENERATION
# ─────────────────────────────────────────────

def generate_markdown(session: DeliberationSession) -> str:
    """Build the complete markdown document from a DeliberationSession."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    task_label = session.task_type.upper()

    consensus = session.final_consensus
    if consensus:
        status_line = (
            f"**{'✓ REACHED' if session.success else '⚠ NOT FULLY REACHED'}** "
            f"({consensus.score}/100)"
        )
    else:
        status_line = "N/A"

    lines = []

    # ── Header ──
    lines.append(f"# ProductCouncil Report: {task_label}")
    lines.append(f"**Date:** {now}  ")
    lines.append(f"**Rounds Completed:** {len(session.rounds)}  ")
    lines.append(f"**Council:** {', '.join(PERSONAS[k]['name'] for k in session.active_ais)}  ")
    lines.append(f"**Consensus Status:** {status_line}  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Query ──
    lines.append("## Query")
    lines.append("")
    lines.append(f"> {session.query}")
    lines.append("")

    if session.context:
        lines.append("## Context Provided")
        lines.append("")
        lines.append(session.context)
        lines.append("")

    # ── Consensus Summary ──
    lines.append("## Council Consensus")
    lines.append("")
    if consensus:
        lines.append(f"**Status:** {'REACHED' if session.success else 'NOT FULLY REACHED'}")
        lines.append(f"**Score:** {consensus.score}/100 _(threshold: 80)_")
        lines.append(f"**Rationale:** {consensus.rationale}")
        lines.append("")
        if consensus.key_agreements:
            lines.append("**Points of Agreement:**")
            for a in consensus.key_agreements:
                lines.append(f"- {a}")
        if consensus.key_disagreements:
            lines.append("")
            lines.append("**Remaining Disagreements:**")
            for d in consensus.key_disagreements:
                lines.append(f"- {d}")
        else:
            lines.append("")
            lines.append("**Remaining Disagreements:** None")
    else:
        lines.append("_Consensus data not available._")

    if not session.success and session.failure_reason:
        lines.append("")
        lines.append(f"> ⚠ **Note:** {session.failure_reason}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Final Answer ──
    lines.append("## Final Answer")
    lines.append("")
    lines.append(session.final_answer or "_No final answer produced._")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Deliberation Transcript ──
    lines.append("## Deliberation Transcript")
    lines.append("")
    lines.append(
        "_The full reasoning chain from all council members across all rounds._"
    )
    lines.append("")

    round_names = {
        1: "Round 1 — Independent Responses",
        2: "Round 2 — Critique & Challenges",
        3: "Round 3 — Final Synthesis",
    }

    for i, round_result in enumerate(session.rounds):
        round_heading = round_names.get(round_result.round_number, f"Round {round_result.round_number}")
        lines.append(f"### {round_heading}")
        lines.append("")

        for ai_key, response in round_result.responses.items():
            ai_info = PERSONAS.get(ai_key, {"name": ai_key, "role": ""})
            lines.append(f"#### {ai_info['name']} ({ai_info['role']})")
            lines.append("")
            lines.append(response)
            lines.append("")

        # Consensus check for this round
        if i < len(session.consensus_checks):
            c = session.consensus_checks[i]
            lines.append(f"#### Round {round_result.round_number} Consensus Check")
            lines.append("")
            lines.append(f"**Score:** {c.score}/100")
            lines.append(f"**Rationale:** {c.rationale}")
            if c.key_agreements:
                lines.append(f"**Agreements:** {', '.join(c.key_agreements)}")
            if c.key_disagreements:
                lines.append(f"**Disputes:** {', '.join(c.key_disagreements)}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── Footer ──
    ts_full = datetime.now(timezone.utc).isoformat()
    lines.append(f"_Generated by ProductCouncil | {ts_full}_")

    return "\n".join(lines)


def save_markdown(content: str, output_path: Path) -> None:
    """Write markdown content to file, creating parent directories if needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
# PDF GENERATION
# ─────────────────────────────────────────────

class CouncilReportPDF:
    """Generate a styled ProductCouncil PDF report."""

    def __init__(self, output_path: str):
        self.output_path = output_path
        self.width, self.height = letter
        self.c = canvas.Canvas(output_path, pagesize=letter)
        self.margin = 0.75 * inch
        self.page_num = 0

    # ── Page Primitives ──

    def _new_page(self) -> None:
        self.c.showPage()
        self.page_num += 1

    def _draw_footer(self, label: str) -> None:
        self.c.setFillColor(NAVY)
        self.c.rect(0, 0, self.width, 32, fill=1, stroke=0)
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica", 8)
        self.c.drawString(self.margin, 10, f"ProductCouncil | {label}")
        self.c.drawRightString(self.width - self.margin, 10, f"Page {self.page_num}")

    def _draw_section_bar(self, y: float, title: str) -> float:
        """Draw a navy section header bar. Returns new y position."""
        self.c.setFillColor(NAVY)
        self.c.rect(0, y - 4, self.width, 26, fill=1, stroke=0)
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica-Bold", 11)
        self.c.drawString(self.margin, y + 6, title.upper())
        return y - 20

    def _wrap_text(self, text: str, max_width: float, font: str, size: int) -> list[str]:
        """Wrap text to fit within max_width pixels."""
        self.c.setFont(font, size)
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            if self.c.stringWidth(test, font, size) <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _draw_wrapped_text(
        self,
        text: str,
        x: float,
        y: float,
        max_width: float,
        font: str = "Helvetica",
        size: int = 10,
        line_height: int = 14,
        color=None,
        min_y: float = 60,
    ) -> float:
        """
        Draw wrapped text, starting a new page if needed.
        Returns final y position.
        """
        if color:
            self.c.setFillColor(color)
        self.c.setFont(font, size)

        paragraphs = text.split("\n")
        for para in paragraphs:
            if not para.strip():
                y -= line_height // 2
                continue

            wrapped_lines = self._wrap_text(para.strip(), max_width, font, size)
            for line in wrapped_lines:
                if y < min_y:
                    self._new_page()
                    self.c.setFillColor(CREAM_BG)
                    self.c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
                    y = self.height - self.margin
                    self._draw_footer("Continued")
                    if color:
                        self.c.setFillColor(color)
                    self.c.setFont(font, size)

                self.c.drawString(x, y, line)
                y -= line_height

        return y

    # ── Pages ──

    def create_cover_page(self, session: DeliberationSession) -> None:
        """Dark cover page with council title, task type, and consensus badge."""
        self.page_num = 1

        # Dark background
        self.c.setFillColor(NAVY)
        self.c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        # Accent bar at top
        self.c.setFillColor(ACCENT)
        self.c.rect(0, self.height - 12, self.width, 12, fill=1, stroke=0)

        # Main title
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica-Bold", 52)
        self.c.drawString(self.margin, self.height - 100, "Product")
        self.c.setFillColor(ACCENT)
        self.c.drawString(self.margin, self.height - 162, "Council")

        # Task type badge
        task_label = session.task_type.upper()
        self.c.setFillColor(ACCENT)
        self.c.roundRect(self.margin, self.height - 220, 120, 30, 4, fill=1, stroke=0)
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica-Bold", 11)
        self.c.drawCentredString(self.margin + 60, self.height - 200, task_label)

        # Date
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica", 12)
        date_str = datetime.now().strftime("%B %d, %Y")
        self.c.drawString(self.margin, self.height - 260, date_str)

        # Council members list
        self.c.setFont("Helvetica-Bold", 11)
        self.c.setFillColor(ACCENT)
        self.c.drawString(self.margin, self.height - 310, "Council Members")
        self.c.setFont("Helvetica", 11)
        self.c.setFillColor(WHITE)
        y = self.height - 330
        for ai_key in session.active_ais:
            info = PERSONAS[ai_key]
            self.c.drawString(self.margin + 10, y, f"• {info['name']}  —  {info['role']}")
            y -= 18

        # Consensus result circle
        consensus = session.final_consensus
        if consensus:
            cx = self.width - self.margin - 60
            cy = self.height - 340
            status_color = GREEN if session.success else RED
            self.c.setFillColor(status_color)
            self.c.circle(cx, cy, 55, fill=1, stroke=0)

            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica-Bold", 22)
            self.c.drawCentredString(cx, cy + 6, f"{consensus.score}")
            self.c.setFont("Helvetica", 9)
            self.c.drawCentredString(cx, cy - 10, "/ 100")
            self.c.setFont("Helvetica-Bold", 8)
            status_text = "CONSENSUS" if session.success else "NO FULL"
            self.c.drawCentredString(cx, cy - 26, status_text)
            if not session.success:
                self.c.drawCentredString(cx, cy - 36, "CONSENSUS")

        # Accent bar at bottom
        self.c.setFillColor(ACCENT)
        self.c.rect(0, 0, self.width, 8, fill=1, stroke=0)

        self._new_page()

    def create_executive_summary(self, session: DeliberationSession) -> None:
        """Page 2 — executive summary with query and final answer."""
        self.c.setFillColor(CREAM_BG)
        self.c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        y = self.height - self.margin

        # Title bar
        y = self._draw_section_bar(y, "Executive Summary")
        y -= 16

        # Query box
        self.c.setFillColor(NAVY)
        self.c.roundRect(self.margin, y - 50, self.width - 2 * self.margin, 60, 4, fill=1, stroke=0)
        self.c.setFillColor(ACCENT)
        self.c.setFont("Helvetica-Bold", 8)
        self.c.drawString(self.margin + 8, y + 2, "QUERY")
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica", 10)
        # Truncate query if very long
        query_display = session.query[:160] + "..." if len(session.query) > 160 else session.query
        y_query = self._draw_wrapped_text(
            query_display,
            x=self.margin + 8,
            y=y - 14,
            max_width=self.width - 2 * self.margin - 16,
            font="Helvetica",
            size=10,
            line_height=14,
            color=WHITE,
        )
        y = min(y - 60, y_query) - 16

        # Consensus strip
        consensus = session.final_consensus
        if consensus:
            status_color = GREEN if session.success else RED
            self.c.setFillColor(status_color)
            self.c.rect(self.margin, y - 2, self.width - 2 * self.margin, 22, fill=1, stroke=0)
            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica-Bold", 10)
            label = f"{'✓' if session.success else '⚠'} Consensus Score: {consensus.score}/100 — {'REACHED' if session.success else 'NOT FULLY REACHED'}"
            self.c.drawString(self.margin + 8, y + 4, label)
            y -= 30

        # Final answer
        y -= 8
        self.c.setFillColor(DARK_GRAY)
        self.c.setFont("Helvetica-Bold", 11)
        self.c.drawString(self.margin, y, "Final Answer")
        y -= 16

        self.c.setStrokeColor(ACCENT)
        self.c.setLineWidth(2)
        self.c.line(self.margin, y, self.width - self.margin, y)
        y -= 12

        final_text = session.final_answer or "No final answer produced."
        y = self._draw_wrapped_text(
            final_text,
            x=self.margin,
            y=y,
            max_width=self.width - 2 * self.margin,
            font="Helvetica",
            size=10,
            line_height=14,
            color=DARK_GRAY,
        )

        self._draw_footer(f"{session.task_type.upper()} | Executive Summary")
        self._new_page()

    def create_transcript_pages(self, session: DeliberationSession) -> None:
        """Create transcript pages — one section per round."""
        round_names = {
            1: "Round 1: Independent Responses",
            2: "Round 2: Critique & Challenges",
            3: "Round 3: Final Synthesis",
        }

        for i, round_result in enumerate(session.rounds):
            # New page for each round
            self.c.setFillColor(CREAM_BG)
            self.c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

            y = self.height - self.margin
            round_heading = round_names.get(round_result.round_number, f"Round {round_result.round_number}")
            y = self._draw_section_bar(y, round_heading)
            y -= 12

            for ai_key, response in round_result.responses.items():
                ai_info = PERSONAS.get(ai_key, {"name": ai_key, "role": ""})

                # AI name header
                if y < 120:
                    self._draw_footer(f"Transcript — {round_heading}")
                    self._new_page()
                    self.c.setFillColor(CREAM_BG)
                    self.c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
                    y = self.height - self.margin

                self.c.setFillColor(ACCENT)
                self.c.setFont("Helvetica-Bold", 10)
                self.c.drawString(self.margin, y, f"{ai_info['name']}  —  {ai_info['role']}")
                y -= 3
                self.c.setStrokeColor(ACCENT)
                self.c.setLineWidth(1)
                self.c.line(self.margin, y, self.margin + 200, y)
                y -= 12

                # Response text
                text_to_draw = response if not response.startswith("ERROR:") else f"[{response}]"
                y = self._draw_wrapped_text(
                    text_to_draw,
                    x=self.margin,
                    y=y,
                    max_width=self.width - 2 * self.margin,
                    font="Helvetica",
                    size=9,
                    line_height=13,
                    color=DARK_GRAY if not response.startswith("ERROR:") else RED,
                )
                y -= 14

            # Consensus check for this round
            if i < len(session.consensus_checks):
                c_result = session.consensus_checks[i]
                if y < 120:
                    self._draw_footer(f"Transcript — {round_heading}")
                    self._new_page()
                    self.c.setFillColor(CREAM_BG)
                    self.c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
                    y = self.height - self.margin

                status_color = GREEN if c_result.meets_threshold else RED
                self.c.setFillColor(status_color)
                self.c.rect(self.margin, y - 4, self.width - 2 * self.margin, 22, fill=1, stroke=0)
                self.c.setFillColor(WHITE)
                self.c.setFont("Helvetica-Bold", 9)
                self.c.drawString(
                    self.margin + 8, y + 4,
                    f"Round {round_result.round_number} Consensus: {c_result.score}/100 — {c_result.rationale[:80]}"
                )
                y -= 30

            self._draw_footer(f"Transcript | Round {round_result.round_number}")
            self._new_page()

    def generate(self, session: DeliberationSession) -> None:
        """Generate the complete PDF."""
        self.create_cover_page(session)
        self.create_executive_summary(session)
        self.create_transcript_pages(session)
        self.c.save()


def generate_pdf(
    markdown_content: str,
    session: DeliberationSession,
    output_path: Path,
) -> None:
    """
    Generate PDF from a DeliberationSession.
    Raises ImportError with instructions if reportlab is not installed.
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError(
            "reportlab is required for PDF generation. "
            "Install it with: pip3 install reportlab"
        )

    pdf = CouncilReportPDF(str(output_path))
    pdf.generate(session)
