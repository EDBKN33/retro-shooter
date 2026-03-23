#!/usr/bin/env python3
"""
ProductCouncil — Deliberation Engine

Orchestrates multi-round deliberation across all 4 AI council members.
Manages rounds, consensus scoring, and session state.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ai_clients import call_all_parallel, call_claude, get_active_ai_keys
from prompts import (
    PERSONAS,
    build_consensus_judge_prompt,
    build_round1_prompt,
    build_round2_prompt,
    build_round3_prompt,
    build_synthesis_prompt,
)


# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class RoundResult:
    round_number: int
    responses: dict[str, str]   # ai_key -> response text
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ConsensusResult:
    score: int                      # 0–100
    rationale: str
    key_agreements: list[str]
    key_disagreements: list[str]
    meets_threshold: bool           # True if score >= threshold


@dataclass
class DeliberationSession:
    task_type: str
    query: str
    context: str
    active_ais: list[str] = field(default_factory=list)
    rounds: list[RoundResult] = field(default_factory=list)
    consensus_checks: list[ConsensusResult] = field(default_factory=list)
    final_answer: Optional[str] = None
    final_consensus: Optional[ConsensusResult] = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    success: bool = False
    failure_reason: Optional[str] = None


# ─────────────────────────────────────────────
# CONSENSUS SCORING
# ─────────────────────────────────────────────

def _parse_consensus_response(raw: str, threshold: int) -> ConsensusResult:
    """Parse Claude judge's structured response into ConsensusResult."""
    # Extract score
    score_match = re.search(r"SCORE:\s*(\d+)", raw)
    score = int(score_match.group(1)) if score_match else 50
    score = max(0, min(100, score))

    # Extract rationale
    rationale_match = re.search(
        r"RATIONALE:\s*(.+?)(?=KEY_AGREEMENTS:|$)", raw, re.DOTALL | re.IGNORECASE
    )
    rationale = rationale_match.group(1).strip() if rationale_match else "Unable to parse rationale."

    # Extract agreements
    agree_match = re.search(
        r"KEY_AGREEMENTS:\s*(.+?)(?=KEY_DISAGREEMENTS:|$)", raw, re.DOTALL | re.IGNORECASE
    )
    agreements_raw = agree_match.group(1).strip() if agree_match else ""
    key_agreements = (
        [a.strip() for a in agreements_raw.split(",") if a.strip()]
        if agreements_raw else []
    )

    # Extract disagreements
    disagree_match = re.search(
        r"KEY_DISAGREEMENTS:\s*(.+?)$", raw, re.DOTALL | re.IGNORECASE
    )
    disagreements_raw = disagree_match.group(1).strip() if disagree_match else "NONE"
    if disagreements_raw.upper().strip() == "NONE":
        key_disagreements = []
    else:
        key_disagreements = [d.strip() for d in disagreements_raw.split(",") if d.strip()]

    return ConsensusResult(
        score=score,
        rationale=rationale,
        key_agreements=key_agreements,
        key_disagreements=key_disagreements,
        meets_threshold=(score >= threshold),
    )


async def check_consensus(
    query: str,
    responses: dict[str, str],
    threshold: int = 80,
) -> ConsensusResult:
    """
    Use Claude as judge to score the consensus level across all responses.
    Returns a ConsensusResult with score 0–100.
    """
    # Filter out ERROR responses from scoring
    valid_responses = [v for v in responses.values() if not v.startswith("ERROR:")]

    if len(valid_responses) < 2:
        return ConsensusResult(
            score=0,
            rationale="Not enough valid responses to evaluate consensus.",
            key_agreements=[],
            key_disagreements=["Insufficient council members responded"],
            meets_threshold=False,
        )

    system_prompt, user_message = build_consensus_judge_prompt(query, valid_responses)

    raw = await call_claude(
        system_prompt=system_prompt,
        user_message=user_message,
        model="claude-opus-4-6",
        max_tokens=500,
    )

    if raw.startswith("ERROR:"):
        # Parse failure fallback
        return ConsensusResult(
            score=50,
            rationale="Consensus check failed; proceeding to next round.",
            key_agreements=[],
            key_disagreements=[],
            meets_threshold=False,
        )

    return _parse_consensus_response(raw, threshold)


# ─────────────────────────────────────────────
# ROUND EXECUTION
# ─────────────────────────────────────────────

async def _run_round(
    round_number: int,
    task_type: str,
    query: str,
    context: str,
    active_ais: list[str],
    previous_responses: Optional[dict[str, str]],
    verbose: bool,
) -> RoundResult:
    """Run one deliberation round and return a RoundResult."""
    round_names = {1: "Independent Responses", 2: "Critique & Challenges", 3: "Final Synthesis"}
    if verbose:
        _print_round_header(round_number, round_names.get(round_number, f"Round {round_number}"))

    prompts: dict[str, tuple[str, str]] = {}

    for ai_key in active_ais:
        if round_number == 1:
            sys_p, usr_p = build_round1_prompt(task_type, query, context, ai_key)
        elif round_number == 2:
            sys_p, usr_p = build_round2_prompt(task_type, query, ai_key, previous_responses or {})
        else:
            sys_p, usr_p = build_round3_prompt(task_type, query, ai_key, previous_responses or {})
        prompts[ai_key] = (sys_p, usr_p)

    if verbose:
        print(f"  Calling {len(prompts)} council members in parallel...")

    responses = await call_all_parallel(prompts)

    if verbose:
        for ai_key, response in responses.items():
            ai_name = PERSONAS[ai_key]["name"]
            status = "✗ ERROR" if response.startswith("ERROR:") else f"✓ {len(response)} chars"
            print(f"    [{status}] {ai_name} ({PERSONAS[ai_key]['role']})")

    return RoundResult(round_number=round_number, responses=responses)


# ─────────────────────────────────────────────
# SYNTHESIS
# ─────────────────────────────────────────────

async def synthesize_consensus_answer(
    task_type: str,
    query: str,
    session: DeliberationSession,
) -> str:
    """
    Produce a clean final answer when consensus is reached before Round 3.
    Uses Claude to synthesize the latest round's agreed-upon responses.
    """
    latest_round = session.rounds[-1]
    valid_responses = [
        v for v in latest_round.responses.values() if not v.startswith("ERROR:")
    ]

    system_prompt, user_message = build_synthesis_prompt(task_type, query, valid_responses)

    result = await call_claude(
        system_prompt=system_prompt,
        user_message=user_message,
        model="claude-opus-4-6",
        max_tokens=2500,
    )

    if result.startswith("ERROR:"):
        # Fallback: return Claude's own latest response
        return latest_round.responses.get(
            "claude", valid_responses[0] if valid_responses else "No valid response available."
        )

    return result


# ─────────────────────────────────────────────
# MAIN DELIBERATION ORCHESTRATOR
# ─────────────────────────────────────────────

async def run_deliberation(
    task_type: str,
    query: str,
    context: str = "",
    max_rounds: int = 3,
    consensus_threshold: int = 80,
    verbose: bool = True,
) -> DeliberationSession:
    """
    Run the full ProductCouncil deliberation protocol.

    Flow:
      Round 1 → consensus check → if ≥threshold, synthesize and done
      Round 2 → consensus check → if ≥threshold, synthesize and done
      Round 3 → consensus check → Round 3 responses ARE the final output

    Returns a completed DeliberationSession.
    """
    active_ais = get_active_ai_keys()

    if len(active_ais) < 2:
        session = DeliberationSession(
            task_type=task_type, query=query, context=context, active_ais=active_ais
        )
        session.success = False
        session.failure_reason = "Council requires at least 2 active AI members. Check your API keys in .env"
        session.completed_at = datetime.now(timezone.utc).isoformat()
        return session

    session = DeliberationSession(
        task_type=task_type,
        query=query,
        context=context,
        active_ais=active_ais,
    )

    if verbose:
        _print_session_info(session, consensus_threshold)

    previous_responses: Optional[dict[str, str]] = None

    for round_num in range(1, min(max_rounds, 3) + 1):
        # Run the round
        round_result = await _run_round(
            round_number=round_num,
            task_type=task_type,
            query=query,
            context=context,
            active_ais=active_ais,
            previous_responses=previous_responses,
            verbose=verbose,
        )
        session.rounds.append(round_result)

        # For round 2, extract the "Proposed Synthesis" sections for consensus checking
        if round_num == 2:
            synthesis_responses = _extract_syntheses(round_result.responses)
            check_responses = synthesis_responses if synthesis_responses else round_result.responses
        else:
            check_responses = round_result.responses

        # Consensus check
        if verbose:
            print(f"\n  Checking consensus...")

        consensus = await check_consensus(query, check_responses, consensus_threshold)
        session.consensus_checks.append(consensus)

        if verbose:
            _print_consensus_result(consensus, consensus_threshold)

        # Decide what to do
        if round_num == 3:
            # Round 3 responses ARE the final answer — use Claude's synthesis
            session.final_consensus = consensus
            session.final_answer = round_result.responses.get(
                "claude",
                next(
                    (v for v in round_result.responses.values() if not v.startswith("ERROR:")),
                    "No valid final answer produced.",
                ),
            )
            session.success = consensus.meets_threshold
            if not session.success:
                session.failure_reason = (
                    f"Consensus not reached after {round_num} rounds "
                    f"(final score: {consensus.score}/100, threshold: {consensus_threshold}). "
                    f"Output includes [DISPUTED:] markers where disagreement remains."
                )
            break

        if consensus.meets_threshold:
            if verbose:
                print(f"\n  ✓ Consensus reached! Synthesizing final answer...")
            session.final_answer = await synthesize_consensus_answer(task_type, query, session)
            session.final_consensus = consensus
            session.success = True
            break

        if round_num < max_rounds:
            if verbose:
                print(f"\n  Consensus not reached ({consensus.score}/100). Proceeding to Round {round_num + 1}...\n")

        # Pass this round's responses to the next round
        previous_responses = round_result.responses

    # Handle case where max_rounds=1 or max_rounds=2 and no consensus
    if session.final_answer is None:
        latest_round = session.rounds[-1]
        session.final_answer = await synthesize_consensus_answer(task_type, query, session)
        latest_consensus = session.consensus_checks[-1] if session.consensus_checks else None
        session.final_consensus = latest_consensus
        session.success = False
        if latest_consensus:
            session.failure_reason = (
                f"Consensus not reached after {len(session.rounds)} round(s) "
                f"(score: {latest_consensus.score}/100). "
                f"Best-effort answer produced."
            )

    session.completed_at = datetime.now(timezone.utc).isoformat()

    if verbose:
        _print_session_complete(session)

    return session


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _extract_syntheses(responses: dict[str, str]) -> dict[str, str]:
    """Extract 'Proposed Synthesis' sections from Round 2 responses for cleaner consensus scoring."""
    syntheses = {}
    for ai_key, response in responses.items():
        if response.startswith("ERROR:"):
            continue
        # Find the Proposed Synthesis section
        match = re.search(
            r"##\s*Proposed Synthesis\s*\n(.*?)(?=##|$)",
            response,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            syntheses[ai_key] = match.group(1).strip()
        else:
            syntheses[ai_key] = response  # fallback to full response
    return syntheses


def _print_round_header(round_number: int, round_name: str) -> None:
    border = "─" * 62
    print(f"\n{border}")
    print(f"  ROUND {round_number}: {round_name.upper()}")
    print(f"{border}")


def _print_consensus_result(result: ConsensusResult, threshold: int) -> None:
    status = "✓ REACHED" if result.meets_threshold else "✗ BELOW THRESHOLD"
    print(f"\n  Consensus Score: {result.score}/100 [{status}]")
    print(f"  Rationale: {result.rationale}")
    if result.key_agreements:
        print(f"  Agreements: {', '.join(result.key_agreements[:3])}")
    if result.key_disagreements:
        print(f"  Disputes:   {', '.join(result.key_disagreements[:3])}")


def _print_session_info(session: DeliberationSession, threshold: int) -> None:
    active_names = [PERSONAS[k]["name"] for k in session.active_ais]
    print(f"\n  Council: {', '.join(active_names)}")
    print(f"  Task:    {session.task_type.upper()}")
    print(f"  Threshold: {threshold}/100")


def _print_session_complete(session: DeliberationSession) -> None:
    border = "═" * 62
    status = "✓ CONSENSUS REACHED" if session.success else "⚠ BEST-EFFORT (no full consensus)"
    score = session.final_consensus.score if session.final_consensus else "N/A"
    print(f"\n{border}")
    print(f"  DELIBERATION COMPLETE")
    print(f"  Status:  {status}")
    print(f"  Score:   {score}/100")
    print(f"  Rounds:  {len(session.rounds)}")
    if not session.success and session.failure_reason:
        print(f"  Note:    {session.failure_reason}")
    print(f"{border}\n")
