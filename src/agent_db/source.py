"""Authored settings: YAML parsing, layer merge, and namespace validation.

Loads the dist and user YAML layers, merges them via append/override
semantics, and validates the resulting dict has only known top-level
namespaces (permissions, claude, codex). The merged dict is then handed
to the emitters (claude.py, codex.py) which project it into each
agent's native config format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

LAYERS = ("dist", "user")
H1 = re.compile(r"^# (?P<title>.+?)\s*$", re.MULTILINE)
SLUG_PARTS = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class Instruction:
    key: str
    title: str
    override: bool
    path: Path
    body: str


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    instructions: tuple[Instruction, ...]

    @property
    def body(self) -> str:
        bodies = []
        for index, instruction in enumerate(self.instructions):
            body = instruction.body.strip()
            if index > 0:
                body = drop_matching_h1(body, self.key)
            if body:
                bodies.append(body)
        return "\n\n".join(bodies).strip() + "\n"


@dataclass(frozen=True)
class SettingsDoc:
    name: str
    path: Path
    data: dict[str, Any]


@dataclass(frozen=True)
class AssetDir:
    name: str
    path: Path


@dataclass(frozen=True)
class SourceLayer:
    name: str
    path: Path
    instructions: tuple[Instruction, ...]
    settings: tuple[SettingsDoc, ...]
    skills: tuple[AssetDir, ...]
    agents: tuple[AssetDir, ...]


@dataclass(frozen=True)
class AgentSource:
    root: Path
    layers: tuple[SourceLayer, ...]

    @classmethod
    def from_roots(cls, defaults: Path, user: Path) -> AgentSource:
        defaults_root = defaults.expanduser().resolve()
        if not defaults_root.is_dir():
            raise NotADirectoryError(defaults_root)

        user_root = user.expanduser().resolve()
        return cls(
            root=user_root,
            layers=(
                load_layer("dist", defaults_root),
                load_layer("user", user_root),
            ),
        )

    @classmethod
    def from_root(cls, root: Path) -> AgentSource:
        resolved = root.expanduser().resolve()
        if not resolved.is_dir():
            raise NotADirectoryError(resolved)

        layers = tuple(
            load_layer(name, resolved / name) for name in LAYERS if (resolved / name).is_dir()
        )
        if not layers:
            raise FileNotFoundError(f"no source layers under {resolved}")
        return cls(root=resolved, layers=layers)


def load_layer(name: str, path: Path) -> SourceLayer:
    return SourceLayer(
        name=name,
        path=path,
        instructions=load_instructions(path / "instructions"),
        settings=load_settings(path),
        skills=load_asset_dirs(path / "skills"),
        agents=load_asset_dirs(path / "agents"),
    )


def load_instructions(path: Path) -> tuple[Instruction, ...]:
    if not path.is_dir():
        return ()
    return tuple(parse_instruction(item) for item in sorted(path.glob("*.md")))


def parse_instruction(path: Path) -> Instruction:
    raw = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(raw)
    title = instruction_title(path, body, frontmatter)
    return Instruction(
        key=slug(title),
        title=title,
        override=bool(frontmatter.get("override", False)),
        path=path,
        body=body.lstrip("\n"),
    )


def split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, raw

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            data = yaml.safe_load("".join(lines[1:index])) or {}
            if not isinstance(data, dict):
                raise ValueError("frontmatter must be a mapping")
            return data, "".join(lines[index + 1 :])
    return {}, raw


def instruction_title(path: Path, body: str, frontmatter: dict[str, Any]) -> str:
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    if path.stem:
        return titleize(path.stem)

    match = H1.search(body)
    if match is not None:
        return match.group("title").strip()
    return "Untitled"


def titleize(value: str) -> str:
    return value.replace("-", " ").replace("_", " ").title()


def slug(value: str) -> str:
    return SLUG_PARTS.sub("-", value.lower()).strip("-")


def drop_matching_h1(body: str, key: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if line.startswith("# ") and slug(line[2:].strip()) == key:
            rest = lines[index + 1 :]
            while rest and not rest[0].strip():
                rest = rest[1:]
            return "\n".join(rest).strip()
        return body
    return body


def load_settings(path: Path) -> tuple[SettingsDoc, ...]:
    docs: list[SettingsDoc] = []
    root_settings = path / "settings.yaml"
    if root_settings.is_file():
        docs.append(parse_settings(root_settings))

    settings_dir = path / "settings"
    if settings_dir.is_dir():
        docs.extend(parse_settings(item) for item in sorted(settings_dir.glob("*.yaml")))
    return tuple(docs)


def parse_settings(path: Path) -> SettingsDoc:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"settings must be a mapping: {path}")
    return SettingsDoc(name=path.stem, path=path, data=data)


def load_asset_dirs(path: Path) -> tuple[AssetDir, ...]:
    if not path.is_dir():
        return ()
    return tuple(
        AssetDir(name=item.name, path=item) for item in sorted(path.iterdir()) if item.is_dir()
    )


def assemble_sections(source: AgentSource) -> tuple[Section, ...]:
    sections: dict[str, Section] = {}
    for layer in source.layers:
        for instruction in layer.instructions:
            existing = sections.get(instruction.key)
            if existing is None or instruction.override:
                sections[instruction.key] = Section(
                    instruction.key,
                    instruction.title,
                    (instruction,),
                )
            else:
                sections[instruction.key] = Section(
                    existing.key,
                    existing.title,
                    (*existing.instructions, instruction),
                )
    return tuple(sections.values())


def merged_skills(source: AgentSource) -> tuple[AssetDir, ...]:
    return merged_assets(source, "skills")


def merged_agents(source: AgentSource) -> tuple[AssetDir, ...]:
    return merged_assets(source, "agents")


def merged_assets(source: AgentSource, attr: str) -> tuple[AssetDir, ...]:
    assets: dict[str, AssetDir] = {}
    for layer in source.layers:
        for asset in getattr(layer, attr):
            assets[asset.name] = asset
    return tuple(assets.values())


def merged_settings(source: AgentSource) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for layer in source.layers:
        for doc in layer.settings:
            apply_settings_doc(merged, doc.data)
    return merged


def doc_settings(doc: SettingsDoc) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    apply_settings_doc(merged, doc.data)
    return merged


def render_restrictions(settings: dict[str, Any]) -> str:
    permissions = settings.get("permissions", {})
    if not isinstance(permissions, dict):
        return ""

    lines = []
    commands = permissions.get("commands", {})
    if isinstance(commands, dict):
        for pattern in commands.get("deny", []):
            lines.append(f"- Never run '{command_subject(pattern)}' or any command matching it.")

    paths = permissions.get("paths", {})
    if isinstance(paths, dict):
        deny = paths.get("deny", [])
        path_rules = [(rule["path"], set(rule.get("permissions", []))) for rule in deny]
        for permission, phrase in [
            ("edit", "edit files"),
            ("glob", "enumerate file paths"),
            ("read", "read files"),
            ("write", "write to files"),
        ]:
            for path, permissions_set in path_rules:
                if permission in permissions_set:
                    lines.append(f"- Never {phrase} matching {path}.")

    if not lines:
        return ""
    return "## Enforced Restrictions\n\n" + "\n".join(lines)


def command_subject(pattern: str) -> str:
    return pattern[:-2] if pattern.endswith(" *") else pattern


def apply_settings_doc(target: dict[str, Any], data: dict[str, Any]) -> None:
    if "append" not in data and "override" not in data:
        merge_append(target, data)
        return

    append = data.get("append")
    if append is not None:
        if not isinstance(append, dict):
            raise ValueError("append settings must be a mapping")
        merge_append(target, append)

    override = data.get("override")
    if override is not None:
        if not isinstance(override, dict):
            raise ValueError("override settings must be a mapping")
        merge_override(target, override)


def merge_append(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        existing = target.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merge_append(existing, value)
        elif isinstance(existing, list) and isinstance(value, list):
            existing.extend(value)
        else:
            target[key] = copy_value(value)


def merge_override(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        target[key] = copy_value(value)


def copy_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: copy_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [copy_value(item) for item in value]
    return value


VALID_NAMESPACES = frozenset({"permissions", "claude", "codex"})


def validate_namespaces(settings: dict[str, Any]) -> None:
    unknown = set(settings) - VALID_NAMESPACES
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(
            f"unknown top-level settings: {names} (agent settings belong under claude: or codex:)"
        )
