"""Prompt builders. Prompts are in English; the output language is set per request."""

from __future__ import annotations

import re

PLATFORM_STYLE = {
    "x": (
        "one post for X (Twitter): punchy, one clear idea, conversational. "
        "No thread numbering such as '1/'."
    ),
    "linkedin": (
        "one LinkedIn post: a strong first line, short paragraphs separated by blank "
        "lines, professional but human, ending with a takeaway or a question when it fits."
    ),
    "facebook": (
        "one Facebook Page post: warm and conversational, short paragraphs, "
        "inviting comments when it fits."
    ),
}


def _brand_block(content: dict) -> str:
    name = content.get("brand_name") or "(not specified)"
    about = content.get("about") or "(not specified)"
    voice = content.get("brand_voice") or "(no special rules)"
    return (
        f"<brand>\nName: {name}\nAbout: {about}\n</brand>\n\n"
        f"<voice_and_rules>\n{voice}\n</voice_and_rules>"
    )


def _language_line(content: dict) -> str:
    language = (content.get("language") or "").strip()
    return f"Write in {language}." if language else "Write in the same language as the topic."


def post_system(content: dict) -> str:
    return (
        "You are an experienced social media copywriter writing on behalf of the brand below. "
        "Follow its voice and rules.\n\n"
        f"{_brand_block(content)}\n\n"
        "Always:\n"
        "- Output only the post text, ready to publish: no title, no preamble, no quotation "
        "marks around it, no notes, no alternatives.\n"
        "- Plain text only, no Markdown (no **bold**, no headings).\n"
        "- Never invent facts, statistics, prices, dates, quotes, testimonials or links. "
        "If something specific is unknown, stay general.\n"
        "- Never mention that the text was written by AI."
    )


def post_prompt(*, topic: str, platform: str, target: int, limit: int, content: dict, instructions: str = "") -> str:
    style = PLATFORM_STYLE.get(platform, "one social media post.")
    lines = [
        f"Write {style}",
        f"Length: at most {target} characters (hard platform limit: {limit}).",
        _language_line(content),
        f"Topic: {topic}",
    ]
    if instructions.strip():
        lines.append(f"Extra instructions from the user: {instructions.strip()}")
    return "\n".join(lines)


def shorten_prompt(*, text: str, count: int, target: int, limit: int) -> str:
    return (
        f"The post below is {count} characters, but it must be at most {target} characters "
        f"(hard limit {limit}). Rewrite it shorter, keeping the language, tone and main point. "
        "Output only the rewritten post.\n\n"
        f"<post>\n{text}\n</post>"
    )


def topics_system(content: dict) -> str:
    return (
        "You are a social media strategist for the brand below.\n\n"
        f"{_brand_block(content)}"
    )


def topics_prompt(content: dict, count: int) -> str:
    return (
        f"Suggest {count} specific, varied topics for this brand's social media posts: a mix of "
        "practical tips, behind the scenes, answers to common customer questions, lessons "
        "learned and industry trends. Each topic is one line of at most 14 words. "
        f"{_language_line(content).replace('the topic', 'the brand information')} "
        f"Output exactly {count} lines, with no numbering, bullets or quotation marks, and nothing else."
    )


IMAGE_PROMPT_SYSTEM = "You write prompts for an AI image generator."


def image_prompt_request(post_text: str) -> str:
    return (
        "Write one prompt (at most 70 words) for an image to accompany the social media post "
        "below. Describe the subject, setting, style, composition, colours and lighting. "
        "The image must contain no text, letters, logos or watermarks. Write the prompt in "
        "English. Output only the prompt.\n\n"
        f"<post>\n{post_text}\n</post>"
    )


IMAGE_SUFFIX = " No text, letters, logos or watermarks in the image."

_WRAPPING_QUOTES = [('"', '"'), ("“", "”"), ("«", "»"), ("'", "'")]
_LIST_MARKER = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s*")


def clean_output(text: str) -> str:
    """Trim whitespace and quotation marks wrapped around the whole text."""
    text = text.strip()
    for left, right in _WRAPPING_QUOTES:
        if len(text) >= 2 and text.startswith(left) and text.endswith(right):
            inner = text[len(left):-len(right)]
            # Only strip when the quotes wrap everything, not e.g. '"Hi" she said "bye"'.
            if left not in inner and right not in inner:
                text = inner.strip()
            break
    return text


def parse_lines(text: str, limit: int) -> list[str]:
    seen, items = set(), []
    for line in text.splitlines():
        line = _LIST_MARKER.sub("", line).strip().strip('"“”«»').strip()
        if not line or line.lower() in seen:
            continue
        seen.add(line.lower())
        items.append(line)
        if len(items) == limit:
            break
    return items
