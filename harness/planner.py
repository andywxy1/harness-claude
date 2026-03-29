"""Planner agent — runs once to produce a sprint plan from a project description."""

from harness.claude_session import call_claude, fresh_session_id
from harness.events import bus
from harness.prompts.planner import PLANNER_SYSTEM
from harness.utils import parse_sprint_plan


def run_planner(project_description: str, workspace: str) -> tuple[str, list[dict]]:
    """Generate a sprint plan from a project description.

    Calls Claude once with the project description and parses the
    response into a vision statement and list of sprint specs.
    """
    bus.emit("agent_start", agent="planner")

    session_id = fresh_session_id()

    prompt = (
        "Generate a sprint plan for the following project. "
        "Do NOT explore the codebase. Do NOT use any tools. "
        "ONLY output the sprint plan in the specified format.\n\n"
        f"PROJECT: {project_description}\n\n"
        "Output the sprint plan now, starting with ---BEGIN SPRINT PLAN--- "
        "and ending with ---END SPRINT PLAN---."
    )

    response = call_claude(
        prompt=prompt,
        session_id=session_id,
        system_prompt=PLANNER_SYSTEM,
        workspace=workspace,
        is_first_turn=True,
        allowed_tools="",  # no tools — planner only outputs text
    )

    bus.emit("agent_output", agent="planner", text=response)
    bus.emit("agent_done", agent="planner")

    vision, sprints = parse_sprint_plan(response)

    bus.emit("log", source="Planner",
             message=f"Produced {len(sprints)} sprint(s)")

    return vision, sprints
