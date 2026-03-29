"""Scans for available skills and agents on the system.

Discovery is universal — reads installed_plugins.json to find all plugins,
then scans each plugin's installPath for skills and agents.
"""

import json
from pathlib import Path


def _get_claude_dir() -> Path:
    return Path.home() / ".claude"


def _get_installed_plugins() -> dict[str, dict]:
    """Read installed_plugins.json and return plugin name → info mapping.

    Returns dict like: {"superpowers@superpowers-marketplace": {"installPath": "...", ...}}
    """
    plugins_file = _get_claude_dir() / "plugins" / "installed_plugins.json"
    if not plugins_file.exists():
        return {}
    try:
        data = json.loads(plugins_file.read_text(encoding="utf-8"))
        plugins = data.get("plugins", {})
        # Each plugin has a list of installs — take the first (most recent)
        result = {}
        for name, installs in plugins.items():
            if isinstance(installs, list) and installs:
                result[name] = installs[0]
            elif isinstance(installs, dict):
                result[name] = installs
        return result
    except (json.JSONDecodeError, OSError):
        return {}


def scan_skills() -> list[dict]:
    """Discover all available skills from user dir and all installed plugins.

    Returns list of dicts: [{"id": str, "name": str, "path": str, "source": str, "description": str}]
    """
    skills = []
    seen_ids = set()

    def _add_skill(sid: str, skill_file: Path, source: str):
        if sid in seen_ids:
            return
        seen_ids.add(sid)
        desc = _extract_skill_description(skill_file)
        skills.append({
            "id": sid,
            "name": sid.split(":")[-1].replace("-", " ").title(),
            "path": str(skill_file),
            "source": source,
            "description": desc,
        })

    # 1. User-installed skills (~/.claude/skills/)
    user_skills_dir = _get_claude_dir() / "skills"
    if user_skills_dir.exists():
        for skill_dir in sorted(user_skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    _add_skill(skill_dir.name, skill_file, "user")

    # 2. All installed plugins — scan each for skills/
    plugins = _get_installed_plugins()
    for plugin_name, plugin_info in plugins.items():
        install_path = Path(plugin_info.get("installPath", ""))
        if not install_path.exists():
            continue

        # Derive a clean source name from plugin identifier
        source = plugin_name.split("@")[0] if "@" in plugin_name else plugin_name

        # Scan common skill locations within the plugin
        skill_dirs_to_check = [
            install_path / "skills",
            install_path / "source" / "skills",
            install_path / ".claude" / "skills",
        ]

        for skills_root in skill_dirs_to_check:
            if not skills_root.exists():
                continue
            for skill_dir in sorted(skills_root.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        sid = f"{source}:{skill_dir.name}"
                        _add_skill(sid, skill_file, source)

    # 3. Marketplace plugins (may have skills in .claude-plugin structure)
    marketplace_dir = _get_claude_dir() / "plugins" / "marketplaces"
    if marketplace_dir.exists():
        for mp_dir in sorted(marketplace_dir.iterdir()):
            if not mp_dir.is_dir():
                continue
            source = mp_dir.name
            # Check for skills in the marketplace plugin itself
            for skills_root in [mp_dir / "skills", mp_dir / ".claude" / "skills"]:
                if not skills_root.exists():
                    continue
                for skill_dir in sorted(skills_root.iterdir()):
                    if skill_dir.is_dir():
                        skill_file = skill_dir / "SKILL.md"
                        if skill_file.exists():
                            sid = f"{source}:{skill_dir.name}"
                            _add_skill(sid, skill_file, source)

    return skills


def scan_agents() -> list[dict]:
    """Discover all available agents from installed plugins.

    Checks two sources:
    1. registry.json files (like CEO's agent registry)
    2. Individual .md files in agents/ directories

    Returns list of dicts: [{"id": str, "name": str, "domain": str, "description": str, "source": str}]
    """
    agents = []
    seen_ids = set()

    def _add_agent(aid: str, name: str, domain: str, desc: str, source: str):
        if aid in seen_ids:
            return
        seen_ids.add(aid)
        agents.append({
            "id": aid,
            "name": name,
            "domain": domain,
            "description": desc[:150],
            "source": source,
        })

    plugins = _get_installed_plugins()
    for plugin_name, plugin_info in plugins.items():
        install_path = Path(plugin_info.get("installPath", ""))
        if not install_path.exists():
            continue

        source = plugin_name.split("@")[0] if "@" in plugin_name else plugin_name

        # Check for registry.json (structured agent list)
        for registry_path in install_path.rglob("registry.json"):
            try:
                data = json.loads(registry_path.read_text(encoding="utf-8"))
                for agent in data.get("agents", []):
                    aid = agent.get("id", "")
                    if aid:
                        _add_agent(
                            aid,
                            agent.get("display_name", aid),
                            agent.get("domain", "other"),
                            agent.get("description", ""),
                            source,
                        )
            except (json.JSONDecodeError, OSError):
                continue

        # Check for individual agent .md files
        agents_dir = install_path / "agents"
        if agents_dir.exists():
            for agent_file in sorted(agents_dir.glob("*.md")):
                aid = agent_file.stem
                if aid in seen_ids:
                    continue
                name, domain, desc = _parse_agent_frontmatter(agent_file)
                _add_agent(aid, name or aid, domain or "other", desc, source)

    # Also check marketplace plugins for agents
    marketplace_dir = _get_claude_dir() / "plugins" / "marketplaces"
    if marketplace_dir.exists():
        for mp_dir in sorted(marketplace_dir.iterdir()):
            if not mp_dir.is_dir():
                continue
            source = mp_dir.name
            agents_dir = mp_dir / "agents"
            if agents_dir.exists():
                for agent_file in sorted(agents_dir.glob("*.md")):
                    aid = agent_file.stem
                    if aid in seen_ids:
                        continue
                    name, domain, desc = _parse_agent_frontmatter(agent_file)
                    _add_agent(aid, name or aid, domain or "other", desc, source)

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
        # Fallback: first non-empty, non-header line after frontmatter
        past_frontmatter = False
        fm_count = 0
        for line in text.split("\n"):
            if line.strip() == "---":
                fm_count += 1
                if fm_count >= 2:
                    past_frontmatter = True
                continue
            if past_frontmatter:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line[:150]
    except OSError:
        pass
    return ""


def _parse_agent_frontmatter(agent_path: Path) -> tuple[str, str, str]:
    """Extract name, domain, and description from an agent .md frontmatter.

    Returns (name, domain, description).
    """
    name = ""
    domain = ""
    desc = ""
    try:
        text = agent_path.read_text(encoding="utf-8")
        in_frontmatter = False
        for line in text.split("\n"):
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
                continue
            if in_frontmatter:
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("display_name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("domain:"):
                    domain = line.split(":", 1)[1].strip()
                elif line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip()[:150]
    except OSError:
        pass
    return name, domain, desc


def build_skill_registry(selected_skill_ids: list[str], workspace: str) -> str:
    """Build a skill registry file in the workspace for agents to read."""
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
    """Build an agent registry file in the workspace for agents to reference."""
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
