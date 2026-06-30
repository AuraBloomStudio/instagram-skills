"""Detect which publishing backend is configured and format user-facing messages.

The skills support three tiers:

  TIER 0 - manual (default, zero setup)
    No credentials in env. Skills produce the caption (and slide or shot list);
    the user posts it in the Instagram app with their own media. Works for
    anyone, any setup.

  TIER 1 - publora (recommended, ~2-min setup)
    `PUBLORA_API_KEY` + `INSTAGRAM_PLATFORM_ID` present. On approval the skills
    run the full media flow (create draft, upload the user's image or video,
    schedule) via the Publora REST API. Sign up: https://app.publora.com/signup

  TIER 2 - diy (advanced)
    `INSTAGRAM_SKILLS_CUSTOM_POSTER` set to a command the user built themselves
    (e.g. via Claude Code or Codex on the Instagram Graph API). Skills delegate
    publishing to that custom tool.

`active_backend()` picks the highest-privilege available. `manual_mode_message()`
is what skills show the user when no backend auto-posts. `publish()` is the
high-level wrapper skills should call so SKILL.md files don't repeat the
dispatch.

Instagram note: every post needs media. The writer skills produce the caption,
hook, hashtags, and slide/shot plan; the USER supplies the image or video file.
So `publish()` only auto-posts on the Publora tier when `media` file paths are
provided. With no media, or on the manual tier, it returns a copy-paste caption
block plus a reminder to attach the media in the Instagram app.
"""
from __future__ import annotations
import json
import os
import shlex
import subprocess
from typing import Any, Literal, Optional

BackendName = Literal["publora", "manual", "diy"]
PublishKind = Literal["post", "carousel", "reel", "story"]

PUBLORA_SIGNUP_URL = "https://app.publora.com/signup"


def active_backend() -> BackendName:
    """Return the active publishing backend.

    Priority: publora > diy > manual. Users with Publora configured get
    auto-post even if they also have a custom poster, unless they remove the
    Publora env var.
    """
    if os.getenv("PUBLORA_API_KEY") and os.getenv("INSTAGRAM_PLATFORM_ID"):
        return "publora"
    if os.getenv("INSTAGRAM_SKILLS_CUSTOM_POSTER"):
        return "diy"
    return "manual"


def manual_mode_message(
    draft_text: str, target_url: str, kind: str = "post"
) -> str:
    """Format the copy-paste approval output for the manual/draft-only tier.

    The user has just approved a caption and expects to publish. Since no
    backend is configured (or no media was supplied), we hand them the caption
    plus a reminder that Instagram needs the image or video attached in the app.
    """
    media_hint = {
        "post": "attach your image, then paste the caption",
        "carousel": "add your slides in order (2-10), then paste the caption",
        "reel": "upload your video as a Reel, then paste the caption",
        "story": "upload your story media, then add the caption text",
    }.get(kind, "attach your media, then paste the caption")
    return f"""Caption approved. In the Instagram app, {media_hint}:

```
{draft_text}
```

**Where:** {target_url}

Remember: Instagram will not let you post without at least one image or video.

---

Want this to publish on a schedule instead of copy-paste? Connect Publora in
about 2 minutes:

1. Sign up free at {PUBLORA_SIGNUP_URL}
2. Connect your Instagram Business or Creator account (Channels then Add Channel)
3. Copy your API key (API section in the sidebar)
4. Add to `.env`:
   ```
   PUBLORA_API_KEY=sk_your_key_here
   INSTAGRAM_PLATFORM_ID=instagram-your_id_here
   ```
5. Next time you approve a post and point to your media files, it uploads and
   schedules for you.
"""


def signup_nudge() -> str:
    """One-liner to drop into skill outputs as a soft reminder."""
    return f"Auto-scheduling via Publora. Free signup: {PUBLORA_SIGNUP_URL}"


def publish(
    kind: PublishKind,
    draft_text: str,
    target_url: str,
    **kwargs: Any,
) -> Optional[dict]:
    """Dispatch an approved caption to the active backend.

    One call replaces the per-skill "On approval, adapt to the backend" block.
    Routes to publora / manual / diy based on `active_backend()`.

    Args:
        kind: "post" | "carousel" | "reel" | "story".
        draft_text: The approved caption.
        target_url: Where the post lands. For the manual tier this is shown to
            the user (e.g. the Instagram composer or the account URL).
        **kwargs: Backend-specific payload. For the publora tier:
            - media: list[str] of LOCAL file paths the user supplied. Required
              to auto-publish (Instagram rejects text-only posts). 1 file -> a
              single photo or Reel; 2-10 images -> a carousel in order.
            - platforms: list[str] of platform IDs (defaults to
              [INSTAGRAM_PLATFORM_ID]).
            - scheduled_time: ISO 8601 UTC (optional).
            - platform_settings: e.g. {"instagram": {"videoType": "REELS"}}.

    Returns:
        - publora (with media): dict from PubloraClient.publish_media_post.
        - manual / publora-without-media: {"mode": "manual", "message": ...}.
        - diy: {"mode": "diy", "returncode": int, "stdout": str, "stderr": str}.
        Returns None only if the chosen backend cannot run (missing deps).
    """
    backend = active_backend()
    media = kwargs.get("media") or []

    # Manual tier, or Publora configured but the user has not pointed us at
    # media files yet. Instagram cannot publish without media, so we surface the
    # copy-paste caption block and remind them to attach it.
    if backend == "manual" or (backend == "publora" and not media):
        return {
            "mode": "manual",
            "message": manual_mode_message(draft_text, target_url, kind=kind),
        }

    if backend == "publora":
        # Local import so manual-tier users never need `requests` installed.
        from .publora_client import PubloraClient

        client = PubloraClient()
        platform_id = kwargs.get("platform_id") or os.getenv("INSTAGRAM_PLATFORM_ID")
        platforms = kwargs.get("platforms") or ([platform_id] if platform_id else [])

        platform_settings = kwargs.get("platform_settings")
        if platform_settings is None and kind in ("reel", "story"):
            video_type = "STORIES" if kind == "story" else "REELS"
            platform_settings = {"instagram": {"videoType": video_type}}

        return client.publish_media_post(
            content=draft_text,
            platforms=platforms,
            media=media,
            scheduled_time=kwargs.get("scheduled_time"),
            platform_settings=platform_settings,
        )

    if backend == "diy":
        cmd = os.getenv("INSTAGRAM_SKILLS_CUSTOM_POSTER")
        if not cmd:
            return None
        payload = {
            "kind": kind,
            "draft_text": draft_text,
            "target_url": target_url,
            **kwargs,
        }
        # The user's poster receives JSON on stdin and kind/target as argv.
        argv = shlex.split(cmd) + [kind, target_url]
        proc = subprocess.run(
            argv,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "mode": "diy",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    raise RuntimeError(f"unknown backend: {backend!r}")


if __name__ == "__main__":
    print(f"Active backend: {active_backend()}")
    if active_backend() == "manual":
        print("\nExample manual message:")
        print("-" * 60)
        print(
            manual_mode_message(
                draft_text="the post that took me 2 years to write..",
                target_url="https://www.instagram.com/",
                kind="carousel",
            )
        )
