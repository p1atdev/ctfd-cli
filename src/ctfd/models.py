from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CtfdModel(BaseModel):
    """Base model that preserves fields added by CTFd plugins."""

    model_config = ConfigDict(extra="allow")


class Pagination(CtfdModel):
    page: int | None = None
    next: int | None = None
    prev: int | None = None
    pages: int | None = None
    per_page: int | None = None
    total: int | None = None


class Hint(CtfdModel):
    id: int
    cost: int = 0
    title: str | None = None
    content: str | None = None
    requirements: list[int] | None = None


class ChallengeSummary(CtfdModel):
    id: int
    type: str | None = None
    name: str
    value: int | float = 0
    category: str | None = None
    position: int | None = None
    solves: int | None = None
    solved_by_me: bool = False
    tags: list[Any] = Field(default_factory=list)
    template: str | None = None
    script: str | None = None


class ChallengeDetail(ChallengeSummary):
    description: str | None = None
    connection_info: str | None = None
    max_attempts: int | None = None
    attempts: int | None = None
    files: list[str] = Field(default_factory=list)
    hints: list[Hint] = Field(default_factory=list)
    requirements: dict[str, Any] | None = None
    state: str | None = None
    logic: str | None = None
    solution_id: int | None = None
    solution_state: str | None = None
    view: str | None = None


class AttemptResult(CtfdModel):
    status: str
    message: str | None = None


class ScoreboardMember(CtfdModel):
    id: int
    name: str
    score: int | float = 0
    oauth_id: str | int | None = None
    bracket_id: int | None = None
    bracket_name: str | None = None


class ScoreboardEntry(CtfdModel):
    pos: int
    account_id: int
    account_url: str | None = None
    account_type: str | None = None
    name: str
    score: int | float = 0
    oauth_id: str | int | None = None
    bracket_id: int | None = None
    bracket_name: str | None = None
    members: list[ScoreboardMember] = Field(default_factory=list)


class User(CtfdModel):
    id: int
    name: str
    email: str | None = None
    score: int | float = 0
    place: int | None = None
    team_id: int | None = None
    oauth_id: str | int | None = None
    verified: bool | None = None
    country: str | None = None
    website: str | None = None
    affiliation: str | None = None
    bracket_id: int | None = None
    bracket_name: str | None = None
    fields: list[dict[str, Any]] = Field(default_factory=list)


class Submission(CtfdModel):
    id: int
    challenge_id: int
    user_id: int | None = None
    team_id: int | None = None
    type: str | None = None
    provided: str | None = None
    date: str | None = None
    challenge: ChallengeSummary | dict[str, Any] | None = None


class Unlock(CtfdModel):
    id: int
    target: int
    type: str
    user_id: int | None = None
    team_id: int | None = None
    date: str | None = None
