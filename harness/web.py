"""Web server for real-time UI — FastAPI + WebSocket.

Can run in two modes:
1. Standalone: `python -m harness.cli` — starts web server, user gives commands via browser
2. Attached: `python -m harness.cli "prompt"` — starts web server alongside CLI-driven orchestrator
"""

import asyncio
import json
import threading
from pathlib import Path

from harness.events import bus

_app = None
_clients: set = set()
_loop: asyncio.AbstractEventLoop | None = None
_orchestrator_thread: threading.Thread | None = None


def _get_app():
    global _app
    if _app is not None:
        return _app

    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse

    _app = FastAPI(title="Harness Claude")

    @_app.get("/")
    async def index():
        html_path = Path(__file__).parent / "static" / "index.html"
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    @_app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        _clients.add(ws)
        try:
            # Send current state snapshot + history on connect
            await ws.send_json({
                "type": "state_snapshot",
                "state": bus.state,
                "history": bus.history[-200:],
            })
            # Listen for client commands
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                cmd = msg.get("command")
                if cmd == "ping":
                    await ws.send_json({"type": "pong"})
                elif cmd == "start_project":
                    _handle_start_project(msg)
                elif cmd == "stop_project":
                    _handle_stop_project()

        except WebSocketDisconnect:
            pass
        finally:
            _clients.discard(ws)

    return _app


def _handle_start_project(msg: dict):
    """Start the orchestrator in a background thread from a web UI command."""
    global _orchestrator_thread

    if _orchestrator_thread and _orchestrator_thread.is_alive():
        bus.emit("error", message="A project is already running.")
        return

    prompt = msg.get("prompt", "").strip()
    workspace = msg.get("workspace", "").strip()

    if not prompt:
        bus.emit("error", message="No project description provided.")
        return

    if not workspace:
        workspace = str(Path.cwd() / "workspace")

    def _run_orchestrator():
        from harness.orchestrator import run_project
        try:
            run_project(prompt, workspace, web=False)  # web=False since server is already running
        except Exception as e:
            bus.emit("error", message=f"Orchestrator crashed: {e}")

    _orchestrator_thread = threading.Thread(target=_run_orchestrator, daemon=True)
    _orchestrator_thread.start()
    bus.emit("log", source="Web", message=f"Project started: {prompt[:100]}")


def _handle_stop_project():
    """Signal the orchestrator to stop."""
    global _orchestrator_thread
    if _orchestrator_thread and _orchestrator_thread.is_alive():
        bus.emit("log", source="Web", message="Stop requested — project will halt after current agent finishes")
        bus.emit("stop_requested")
    else:
        bus.emit("log", source="Web", message="No project running.")
        bus.emit("stop_requested")  # still emit so UI resets


def _on_event(event: dict):
    """Bridge sync event → async WebSocket broadcast."""
    if _loop is None or not _clients:
        return
    asyncio.run_coroutine_threadsafe(_broadcast(event), _loop)


async def _broadcast(event: dict):
    """Send event to all connected WebSocket clients."""
    dead = set()
    for ws in _clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


def start_web_server(port: int = 8420, block: bool = False):
    """Start uvicorn. If block=True, runs on main thread (standalone mode).

    Args:
        port: Port number.
        block: If True, blocks the main thread (for standalone web mode).
    """
    global _loop

    import uvicorn

    app = _get_app()
    bus.subscribe(_on_event)

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    if block:
        # Standalone mode — web server IS the main process
        print(f"Harness Claude UI running at http://localhost:{port}")
        print("Open in your browser to start a project.")
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _loop.run_until_complete(server.serve())
    else:
        # Attached mode — web server runs alongside CLI orchestrator
        def _run():
            global _loop
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
            _loop.run_until_complete(server.serve())

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        bus.emit("log", source="Web", message=f"UI available at http://localhost:{port}")
