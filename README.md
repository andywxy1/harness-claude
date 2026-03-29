# Harness Claude

A Generator-Evaluator orchestration harness for [Claude Code](https://claude.ai/code). Inspired by [Anthropic's harness design patterns](https://www.anthropic.com/engineering/harness-design-long-running-apps) and multi-agent debate architectures.

Harness Claude splits complex software projects into sprints, then uses adversarial Generator and Evaluator agents to negotiate contracts, implement code, and verify quality — with a real-time mission-control web UI.

## How It Works

```
Planner (once)
  |
  v
For each sprint:
  1. CONTRACT NEGOTIATION
     Generator proposes features + tests
     Evaluator critiques for rigor and testability
     They negotiate until both AGREE

  2. IMPLEMENTATION
     Generator builds (persistent context across fix cycles)
     Generator self-tests before handing off
     Evaluator tests independently (fresh context each cycle)
     If same failure 3x → rollback to renegotiation

  3. EVALUATION
     Evaluator runs contract tests
     Evaluator uses the product as a real user
     Reports PASS/FAIL with P0-P3 severity

Final Review → senior engineer reviews entire codebase
```

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Claude Code CLI** installed and authenticated (`claude` command available)
- **Node.js** (for Claude Code)

### Install

```bash
git clone https://github.com/YOUR_USERNAME/harness-claude.git
cd harness-claude
pip install -e .
```

### Run

**Web UI mode** (recommended):
```bash
harness-claude
# Opens at http://localhost:8420
# Type your project description in the browser and click Launch
```

**CLI mode with web monitoring**:
```bash
harness-claude "Build a todo app with real-time collaboration" -w ./my-project
# Web UI streams progress at http://localhost:8420
```

**CLI mode only** (no web):
```bash
harness-claude "Build a todo app" --no-web -w ./my-project
```

### Options

```
harness-claude [prompt] [options]

Arguments:
  prompt                Project description (optional — omit for web UI mode)

Options:
  -w, --workspace PATH  Project workspace directory (default: ./workspace)
  --no-web              Console-only mode (requires prompt)
  --port PORT           Web UI port (default: 8420)
  -h, --help            Show help
```

## Web UI

The mission-control web UI shows:

- **Sprint progress bar** — track which sprint is active
- **Phase pipeline** — see negotiation rounds, implementation cycles, evaluation results
- **Chat bubbles** — generator and evaluator messages with markdown rendering
- **Contract view** — the agreed sprint contract with full test specifications
- **Eval report** — checklist of PASS/FAIL items with severity badges
- **Event log** — raw debug output
- **Settings** — configure which Claude model each agent uses (Opus/Sonnet/Haiku)
- **Folder picker** — native macOS Finder dialog for selecting workspace

## Architecture

```
harness/
├── cli.py                  # Entry point
├── orchestrator.py         # Sprint sequencing + deferred item carry-over
├── planner.py              # Splits project into sprint themes
├── negotiation.py          # Generator-Evaluator contract negotiation
├── implementation.py       # Build/test cycles with rollback
├── review.py               # Final codebase review
├── config.py               # Runtime model + timeout configuration
├── claude_session.py       # Claude Code CLI wrapper (--resume sessions)
├── events.py               # Event bus (sync → async bridge)
├── utils.py                # Git, parsing, file helpers
├── web.py                  # FastAPI + WebSocket server
├── static/index.html       # Single-file web UI
└── prompts/
    ├── contract_criteria.py  # Shared contract quality rubric
    ├── planner.py            # Planner system prompt
    ├── negotiation.py        # Negotiation system prompts
    ├── implementation.py     # Implementation system prompts
    └── review.py             # Final review system prompt
```

### Key Design Decisions

- **Persistent generator sessions** within a sprint (remembers what it tried)
- **Fresh evaluator sessions** each cycle (unbiased assessment)
- **Contract-as-law** — tests defined before code, both agents verify independently
- **Rollback mechanism** — 3 repeated failures trigger contract renegotiation
- **Deferred items** — out-of-scope items carry forward to future sprints
- **No max rounds** for negotiation — agents must reach consensus

### How Agents Communicate

Agents are separate Claude Code CLI invocations sharing a filesystem:
- First turn: `claude -p "prompt" --session-id UUID`
- Subsequent turns: `claude -p "prompt" --resume UUID`
- Context persists via session JSONL files on disk
- The orchestrator manages turn-taking and passes outputs between agents

## Configuration

Click the gear icon in the web UI to configure models per role:

| Role | Default | Description |
|------|---------|-------------|
| Planner | opus | Splits project into sprints |
| Negotiation Generator | opus | Proposes sprint contracts |
| Negotiation Evaluator | opus | Critiques contracts for rigor |
| Implementation Generator | opus | Writes code |
| Implementation Evaluator | opus | Tests and reviews code |
| Reviewer | opus | Final codebase review |

## License

AGPL-3.0 with additional commercial restriction. See [LICENSE](LICENSE).

- Source code modifications must remain open source
- Commercial distribution requires written permission from the copyright holder
- Free for personal, educational, and non-commercial use
