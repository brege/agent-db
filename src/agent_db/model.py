"""Shared policy types for permission rules.

Currently unused by the emitters, which derive permissions from raw
dicts. These types exist as a target for future typed-schema work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Action(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    EXEC = "exec"
    GLOB = "glob"


@dataclass(frozen=True)
class PolicyRule:
    action: Action
    permission: Permission
    pattern: str
