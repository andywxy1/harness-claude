"""CLI entry point for Harness Claude."""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="harness-claude",
        description="Harness Claude — Generator-Evaluator orchestration for Claude Code",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Project description. If omitted, starts the web UI for interactive use.",
    )
    parser.add_argument(
        "-w", "--workspace",
        default=None,
        help="Path to the project workspace directory (default: ./workspace)",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Disable the web UI (console-only mode, requires prompt)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8420,
        help="Port for the web UI (default: 8420)",
    )

    args = parser.parse_args()

    workspace = args.workspace
    if workspace is None:
        workspace = str(Path.cwd() / "workspace")

    try:
        if args.prompt is None:
            # No prompt — start web UI in standalone mode
            if args.no_web:
                parser.error("Cannot use --no-web without a prompt.")
            from harness.web import start_web_server
            start_web_server(port=args.port, block=True)
        elif args.no_web:
            # Prompt + no web — console only
            from harness.orchestrator import run_project
            run_project(args.prompt, workspace, web=False)
        else:
            # Prompt + web — both
            from harness.orchestrator import run_project
            run_project(args.prompt, workspace, web=True, port=args.port)
    except KeyboardInterrupt:
        print("\n\n[Harness] Interrupted. Progress has been git-committed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
