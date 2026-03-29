"""Scans for available skills and agents on the system."""

import json
from pathlib import Path


def scan_skills() -> list[dict]:
    """Discover all available skills and return structured list.

    Returns list of dicts: [{"id": str, "name": str, "path": str, "source": str, "description": str}]
    """
    skills = []
    seen_ids = set()

    # User-installed skills (~/.claude/skills/)
    user_skills_dir = Path.home() / ".claude" / "skills"
    if user_skills_dir.exists():
        for skill_dir in sorted(user_skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    sid = skill_dir.name
                    if sid not in seen_ids:
                        seen_ids.add(sid)
                        desc = _extract_skill_description(skill_file)
                        skills.append({
                            "id": sid,
                            "name": sid.replace("-", " ").title(),
                            "path": str(skill_file),
                            "source": "user",
                            "description": desc,
                        })

    # Impeccable plugin skills
    imp_base = Path.home() / ".claude/plugins/cache/impeccable"
    if imp_base.exists():
        # Find the latest version
        versions = sorted(imp_base.iterdir(), reverse=True)
        for ver_dir in versions:
            source_skills = ver_dir / "source" / "skills"
            if source_skills.exists():
                for skill_dir in sorted(source_skills.iterdir()):
                    if skill_dir.is_dir():
                        skill_file = skill_dir / "SKILL.md"
                        if skill_file.exists():
                            sid = f"impeccable:{skill_dir.name}"
                            if sid not in seen_ids:
                                seen_ids.add(sid)
                                desc = _extract_skill_description(skill_file)
                                skills.append({
                                    "id": sid,
                                    "name": skill_dir.name.replace("-", " ").title(),
                                    "path": str(skill_file),
                                    "source": "impeccable",
                                    "description": desc,
                                })
                break  # only use the first (latest) version

    # Superpowers plugin skills
    sp_dirs = list((Path.home() / ".claude/plugins/cache").glob("temp_git_*/skills"))
    for sp_base in sp_dirs:
        if sp_base.exists():
            for skill_dir in sorted(sp_base.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        sid = f"superpowers:{skill_dir.name}"
                        if sid not in seen_ids:
                            seen_ids.add(sid)
                            desc = _extract_skill_description(skill_file)
                            skills.append({
                                "id": sid,
                                "name": skill_dir.name.replace("-", " ").title(),
                                "path": str(skill_file),
                                "source": "superpowers",
                                "description": desc,
                            })

    return skills


def scan_agents() -> list[dict]:
    """Discover available CEO sub-agents from the registry.

    Returns list of dicts: [{"id": str, "name": str, "domain": str, "description": str}]
    """
    registry_path = (
        Path.home() / ".claude/plugins/marketplaces/ceo/skills/ceo/registry.json"
    )
    if not registry_path.exists():
        return []

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    agents = []
    for agent in data.get("agents", []):
        agents.append({
            "id": agent.get("id", ""),
            "name": agent.get("display_name", agent.get("id", "")),
            "domain": agent.get("domain", "other"),
            "description": agent.get("description", "")[:150],
        })

    return agents


def _extract_skill_description(skill_path: Path) -> str:
    """Extract the description from a skill's YAML frontmatter."""
    try:
        text = skill_path.read_text(encoding="utf-8")
        in_frontmatter = False
        for line in text.split("\n"):
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
                continue
            if in_frontmatter and line.startswith("description:"):
                return line.split(":", 1)[1].strip()[:150]
        # Fallback: first non-empty, non-header line
        for line in text.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("---"):
                return line[:150]
    except OSError:
        pass
    return ""


def build_skill_registry(selected_skill_ids: list[str], workspace: str) -> str:
    """Build a skill registry file in the workspace for agents to read.

    Returns the path to the registry file.
    """
    all_skills = scan_skills()
    selected = [s for s in all_skills if s["id"] in selected_skill_ids]

    registry_content = "# Skill Registry\n\n"
    registry_content += "You have access to the following skills. Each skill is a markdown file\n"
    registry_content += "containing expert instructions. Read the skill file with the Read tool\n"
    registry_content += "before starting related work, then follow its guidelines.\n\n"
    registry_content += "You are in headless (-p) mode — you CANNOT invoke skills interactively.\n"
    registry_content += "Instead: Read the file, understand the guidelines, apply them in one pass.\n\n"

    for s in selected:
        registry_content += f"## {s['name']}\n"
        registry_content += f"- **ID**: {s['id']}\n"
        registry_content += f"- **Path**: {s['path']}\n"
        registry_content += f"- **Description**: {s['description']}\n\n"

    out_path = Path(workspace) / ".orchestrator" / "skill-registry.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(registry_content, encoding="utf-8")
    return str(out_path)


def build_agent_registry(selected_agent_ids: list[str], workspace: str) -> str:
    """Build an agent registry file in the workspace for agents to reference.

    Returns the path to the registry file.
    """
    all_agents = scan_agents()
    selected = [a for a in all_agents if a["id"] in selected_agent_ids]

    # Group by domain
    domains: dict[str, list] = {}
    for a in selected:
        domain = a["domain"]
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(a)

    registry_content = "# Agent Registry\n\n"
    registry_content += "These specialized agents are available for delegation.\n"
    registry_content += "You can reference them when proposing architecture or task breakdown.\n\n"

    for domain in sorted(domains.keys()):
        registry_content += f"## {domain.replace('-', ' ').title()}\n"
        for a in domains[domain]:
            registry_content += f"- **{a['name']}** (`{a['id']}`): {a['description']}\n"
        registry_content += "\n"

    out_path = Path(workspace) / ".orchestrator" / "agent-registry.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(registry_content, encoding="utf-8")
    return str(out_path)
