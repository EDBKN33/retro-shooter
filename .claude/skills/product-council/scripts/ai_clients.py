#!/usr/bin/env python3
"""
ProductCouncil — Async API Wrappers for all 4 AI Council Members

Each function is async and returns a plain string.
Errors are returned as "ERROR: ..." strings rather than raised,
so one AI failure does not kill the council session.
"""

import asyncio
import os

import anthropic
import openai
from dotenv import load_dotenv

load_dotenv()

# Attempt Gemini import — optional dependency
try:
    from google import genai as google_genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ─────────────────────────────────────────────
# CLIENT FACTORIES
# ─────────────────────────────────────────────

def _anthropic_client() -> anthropic.AsyncAnthropic:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set in .env")
    return anthropic.AsyncAnthropic(api_key=key)


def _openai_client() -> openai.AsyncOpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("OPENAI_API_KEY not set in .env")
    return openai.AsyncOpenAI(api_key=key)


def _perplexity_client() -> openai.AsyncOpenAI:
    key = os.getenv("PERPLEXITY_API_KEY")
    if not key:
        raise EnvironmentError("PERPLEXITY_API_KEY not set in .env")
    return openai.AsyncOpenAI(
        api_key=key,
        base_url="https://api.perplexity.ai",
    )


def _get_gemini_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise EnvironmentError("GEMINI_API_KEY not set in .env")
    return google_genai.Client(api_key=key)


# ─────────────────────────────────────────────
# INDIVIDUAL AI CALL FUNCTIONS
# ─────────────────────────────────────────────

async def call_claude(
    system_prompt: str,
    user_message: str,
    model: str = "claude-opus-4-6",
    max_tokens: int = 2000,
) -> str:
    """Call Claude via Anthropic async SDK. Returns response text or ERROR string."""
    try:
        client = _anthropic_client()
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as e:
        return f"ERROR: Claude failed — {type(e).__name__}: {str(e)[:300]}"


async def call_gpt4o(
    system_prompt: str,
    user_message: str,
    model: str = "gpt-4o",
    max_tokens: int = 2000,
) -> str:
    """Call GPT-4o via OpenAI async SDK. Returns response text or ERROR string."""
    try:
        client = _openai_client()
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"ERROR: GPT-4o failed — {type(e).__name__}: {str(e)[:300]}"


async def call_gemini(
    system_prompt: str,
    user_message: str,
    model: str = "gemini-2.5-flash",
    max_tokens: int = 2000,
) -> str:
    """
    Call Gemini via google-generativeai (sync SDK wrapped in asyncio.to_thread).
    Returns response text or ERROR string.
    """
    if not GEMINI_AVAILABLE:
        return "ERROR: Gemini failed — google-generativeai not installed. Run: pip3 install google-generativeai"

    def _sync_call() -> str:
        client = _get_gemini_client()
        result = client.models.generate_content(
            model=model,
            contents=f"{system_prompt}\n\n{user_message}",
            config=google_genai.types.GenerateContentConfig(
                max_output_tokens=max_tokens,
            ),
        )
        # result.text has a known SDK bug — extract via model_dump instead
        d = result.model_dump()
        parts = d.get("candidates", [{}])[0].get("content", {}).get("parts", []) or []
        text_parts = [p["text"] for p in parts if p.get("text") and not p.get("thought")]
        return " ".join(text_parts) if text_parts else ""

    try:
        return await asyncio.to_thread(_sync_call)
    except Exception as e:
        return f"ERROR: Gemini failed — {type(e).__name__}: {str(e)[:300]}"


async def call_perplexity(
    system_prompt: str,
    user_message: str,
    model: str = "sonar-pro",
    max_tokens: int = 2000,
) -> str:
    """
    Call Perplexity via OpenAI-compatible async API.
    Uses sonar-online model which includes real-time web citations.
    Returns response text or ERROR string.
    """
    try:
        client = _perplexity_client()
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"ERROR: Perplexity failed — {type(e).__name__}: {str(e)[:300]}"


# ─────────────────────────────────────────────
# PARALLEL DISPATCH
# ─────────────────────────────────────────────

async def call_all_parallel(
    prompts: dict[str, tuple[str, str]],
) -> dict[str, str]:
    """
    Call all available AIs in parallel using asyncio.gather.

    Args:
        prompts: dict mapping ai_key -> (system_prompt, user_message)
                 ai_key is one of: 'claude', 'gpt4o', 'gemini', 'perplexity'

    Returns:
        dict mapping ai_key -> response_text
    """
    callers = {
        "claude": call_claude,
        "gpt4o": call_gpt4o,
        "gemini": call_gemini,
        "perplexity": call_perplexity,
    }

    tasks = {}
    for ai_key, (sys_prompt, user_msg) in prompts.items():
        if ai_key in callers:
            tasks[ai_key] = asyncio.create_task(
                callers[ai_key](sys_prompt, user_msg)
            )

    if not tasks:
        return {}

    results = await asyncio.gather(*tasks.values())
    return dict(zip(tasks.keys(), results))


# ─────────────────────────────────────────────
# KEY VALIDATION
# ─────────────────────────────────────────────

def validate_api_keys() -> tuple[list[str], list[str]]:
    """
    Check which API keys are present.

    Returns:
        (present, missing) — lists of AI names
    """
    checks = {
        "claude": ("ANTHROPIC_API_KEY", "Claude"),
        "gpt4o": ("OPENAI_API_KEY", "GPT-4o"),
        "gemini": ("GEMINI_API_KEY", "Gemini"),
        "perplexity": ("PERPLEXITY_API_KEY", "Perplexity"),
    }

    present = []
    missing = []
    for ai_key, (env_var, name) in checks.items():
        if os.getenv(env_var):
            present.append(ai_key)
        else:
            missing.append(f"{env_var} ({name})")

    return present, missing


def get_active_ai_keys() -> list[str]:
    """Return list of ai_keys for which API keys are present."""
    present, _ = validate_api_keys()
    return present
