"""Wrapper for calling Claude Code CLI with session management."""

import subprocess
import uuid


def fresh_session_id() -> str:
    return str(uuid.uuid4())


def call_claude(
    prompt: str,
    session_id: str,
    system_prompt: str,
    workspace: str,
    is_first_turn: bool = False,
    timeout: int = 600,
    allowed_tools: str | None = None,
    model: str = "opus",
) -> str:
    """Call Claude Code CLI with session support.

    Args:
        prompt: The user prompt to send.
        session_id: UUID for session tracking.
        system_prompt: Appended system prompt for role behavior.
        workspace: Working directory for the claude process.
        is_first_turn: If True, creates new session. If False, resumes.
        timeout: Max seconds to wait for response.
        allowed_tools: Comma-separated tool names, or empty string to disable all tools.
        model: Model to use (e.g. "opus", "sonnet", "haiku").

    Returns:
        The text response from Claude.
    """
    cmd = [
        "claude",
        "-p", prompt,
        "--append-system-prompt", system_prompt,
        "--dangerously-skip-permissions",
        "--model", model,
    ]

    if allowed_tools is not None:
        cmd.extend(["--allowedTools", allowed_tools])

    if is_first_turn:
        cmd.extend(["--session-id", session_id])
    else:
        cmd.extend(["--resume", session_id])

    result = subprocess.run(
        cmd,
        input="",
        capture_output=True,
        text=True,
        cwd=workspace,
        timeout=timeout,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            print(f"  [claude stderr] {stderr[:300]}")

    return result.stdout.strip()
