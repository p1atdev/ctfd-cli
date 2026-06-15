from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import wraps
from typing import Annotated, Any

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ctfd.client import CtfdClient
from ctfd.config import load_settings
from ctfd.errors import (
    CtfdAuthenticationError,
    CtfdConfigError,
    CtfdConnectionError,
    CtfdError,
    CtfdPermissionError,
    CtfdRateLimitError,
)
from ctfd.models import ChallengeDetail, Hint, Submission, User

EXIT_OPERATION = 1
EXIT_CONFIG = 3
EXIT_AUTH = 4
EXIT_NETWORK = 5
EXIT_API = 6

app = typer.Typer(
    name="ctfd",
    help="Interact with participant-facing CTFd APIs.",
    no_args_is_help=True,
)
challenges_app = typer.Typer(help="List, inspect, and submit challenges.")
me_app = typer.Typer(help="Show your profile and activity.", invoke_without_command=True)
app.add_typer(challenges_app, name="challenges")
app.add_typer(me_app, name="me")

console = Console()
error_console = Console(stderr=True)


@dataclass(frozen=True)
class CliOptions:
    url: str | None
    token: str | None
    timeout: float | None


def _handle_errors[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except CtfdConfigError as exc:
            _print_error(exc)
            raise typer.Exit(EXIT_CONFIG) from None
        except CtfdAuthenticationError as exc:
            _print_error(exc)
            raise typer.Exit(EXIT_AUTH) from None
        except CtfdPermissionError as exc:
            _print_error(exc)
            raise typer.Exit(EXIT_AUTH) from None
        except CtfdRateLimitError as exc:
            suffix = f" (retry after {exc.retry_after}s)" if exc.retry_after else ""
            _print_error(f"{exc}{suffix}")
            raise typer.Exit(EXIT_OPERATION) from None
        except CtfdConnectionError as exc:
            _print_error(exc)
            raise typer.Exit(EXIT_NETWORK) from None
        except CtfdError as exc:
            _print_error(exc)
            raise typer.Exit(EXIT_API) from None

    return wrapper


def _print_error(error: object) -> None:
    error_console.print(Text.assemble(("Error: ", "bold red"), str(error)))


def _client(ctx: typer.Context) -> CtfdClient:
    options = ctx.ensure_object(CliOptions)
    settings = load_settings(
        url=options.url,
        token=options.token,
        timeout=options.timeout,
    )
    return CtfdClient(
        settings.url,
        settings.token,
        timeout=settings.timeout,
    )


def _json_data(value: BaseModel | Sequence[BaseModel] | dict[str, Any]) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Sequence):
        return [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item
            for item in value
        ]
    return value


def _print_json(value: BaseModel | Sequence[BaseModel] | dict[str, Any]) -> None:
    typer.echo(json.dumps(_json_data(value), ensure_ascii=False, indent=2))


@app.callback()
def main(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="CTFd site URL. Defaults to CTFD_URL."),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option("--token", help="CTFd API token. Defaults to CTFD_TOKEN."),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", min=0.1, help="Request timeout in seconds."),
    ] = None,
) -> None:
    """Load global connection options."""

    ctx.obj = CliOptions(url=url, token=token, timeout=timeout)


@challenges_app.command("list")
@_handle_errors
def list_challenges(
    ctx: typer.Context,
    category: Annotated[str | None, typer.Option(help="Filter by category.")] = None,
    challenge_type: Annotated[
        str | None,
        typer.Option("--type", help="Filter by challenge type."),
    ] = None,
    state: Annotated[str | None, typer.Option(help="Filter by state.")] = None,
    query: Annotated[str | None, typer.Option("--search", "-s", help="Search value.")] = None,
    field: Annotated[
        str | None,
        typer.Option(help="Field used by --search, such as name or category."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
) -> None:
    """List visible challenges."""

    with _client(ctx) as client:
        challenges = client.list_challenges(
            category=category,
            challenge_type=challenge_type,
            state=state,
            query=query,
            field=field,
        )

    if json_output:
        _print_json(challenges)
        return

    table = Table(title="Challenges")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Value", justify="right")
    table.add_column("Solves", justify="right")
    table.add_column("Solved")
    for challenge in challenges:
        table.add_row(
            str(challenge.id),
            challenge.name,
            challenge.category or "",
            str(challenge.value),
            "" if challenge.solves is None else str(challenge.solves),
            "yes" if challenge.solved_by_me else "",
        )
    console.print(table)


@challenges_app.command("show")
@_handle_errors
def show_challenge(
    ctx: typer.Context,
    challenge_id: Annotated[int, typer.Argument(min=1, help="Challenge ID.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
) -> None:
    """Show a challenge and its files and hints."""

    with _client(ctx) as client:
        challenge = client.get_challenge(challenge_id)

    if json_output:
        _print_json(challenge)
        return
    _print_challenge(challenge)


def _print_challenge(challenge: ChallengeDetail) -> None:
    details = Table.grid(padding=(0, 2))
    details.add_column(style="bold")
    details.add_column()
    details.add_row("ID", str(challenge.id))
    details.add_row("Category", challenge.category or "")
    details.add_row("Value", str(challenge.value))
    details.add_row("Solves", "" if challenge.solves is None else str(challenge.solves))
    details.add_row("Solved", "yes" if challenge.solved_by_me else "no")
    if challenge.connection_info:
        details.add_row("Connection", challenge.connection_info)
    console.print(Panel(details, title=challenge.name))

    if challenge.description:
        console.print(Markdown(challenge.description))
    if challenge.files:
        console.print("\n[bold]Files[/bold]")
        for file_url in challenge.files:
            console.print(f"- {file_url}")
    if challenge.hints:
        console.print("\n[bold]Hints[/bold]")
        for hint in challenge.hints:
            state = "unlocked" if hint.content is not None else f"{hint.cost} points"
            title = hint.title or f"Hint {hint.id}"
            console.print(f"- {title} (ID {hint.id}, {state})")


@challenges_app.command("submit")
@_handle_errors
def submit_challenge(
    ctx: typer.Context,
    challenge_id: Annotated[int, typer.Argument(min=1, help="Challenge ID.")],
    flag: Annotated[str, typer.Argument(help="Flag or answer to submit.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
) -> None:
    """Submit a flag for a challenge."""

    with _client(ctx) as client:
        result = client.submit_challenge(challenge_id, flag)

    if json_output:
        _print_json(result)
    else:
        style = "bold green" if result.status == "correct" else "bold yellow"
        console.print(Text(result.message or result.status, style=style))
    if result.status not in {"correct", "already_solved"}:
        raise typer.Exit(EXIT_OPERATION)


@challenges_app.command("unlock-hint")
@_handle_errors
def unlock_hint(
    ctx: typer.Context,
    hint_id: Annotated[int, typer.Argument(min=1, help="Hint ID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Unlock without confirmation."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
) -> None:
    """Spend points to unlock a hint."""

    with _client(ctx) as client:
        hint = client.get_hint(hint_id)
        if hint.content is None:
            if not yes:
                prompt = f"Unlock hint {hint_id} for {hint.cost} points?"
                if not typer.confirm(prompt):
                    raise typer.Abort()
            hint = client.unlock_hint(hint_id)

    if json_output:
        _print_json(hint)
    else:
        _print_hint(hint)


def _print_hint(hint: Hint) -> None:
    title = hint.title or f"Hint {hint.id}"
    if hint.content:
        console.print(Panel(Markdown(hint.content), title=title))
    else:
        console.print(f"{title} is locked ({hint.cost} points).")


@app.command("scoreboard")
@_handle_errors
def scoreboard(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
) -> None:
    """Show the public scoreboard."""

    with _client(ctx) as client:
        entries = client.get_scoreboard()

    if json_output:
        _print_json(entries)
        return

    table = Table(title="Scoreboard")
    table.add_column("Place", justify="right")
    table.add_column("Name")
    table.add_column("Score", justify="right")
    for entry in entries:
        table.add_row(str(entry.pos), entry.name, str(entry.score))
    console.print(table)


@me_app.callback()
@_handle_errors
def me(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
) -> None:
    """Show the current user's profile."""

    if ctx.invoked_subcommand is not None:
        return
    with _client(ctx) as client:
        user = client.get_me()
    if json_output:
        _print_json(user)
    else:
        _print_user(user)


def _print_user(user: User) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("ID", str(user.id))
    table.add_row("Name", user.name)
    if user.email:
        table.add_row("Email", user.email)
    table.add_row("Score", str(user.score))
    if user.place is not None:
        table.add_row("Place", str(user.place))
    if user.affiliation:
        table.add_row("Affiliation", user.affiliation)
    if user.country:
        table.add_row("Country", user.country)
    console.print(Panel(table, title="Profile"))


@me_app.command("solves")
@_handle_errors
def my_solves(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
) -> None:
    """Show the current user's successful submissions."""

    with _client(ctx) as client:
        submissions = client.get_my_solves()
    _print_submissions(submissions, json_output=json_output, title="Solves")


@me_app.command("submissions")
@_handle_errors
def my_submissions(
    ctx: typer.Context,
    challenge_id: Annotated[
        int | None,
        typer.Option("--challenge-id", min=1, help="Filter by challenge ID."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
) -> None:
    """Show the current user's submissions."""

    with _client(ctx) as client:
        submissions = client.get_my_submissions(challenge_id=challenge_id)
    _print_submissions(submissions, json_output=json_output, title="Submissions")


def _print_submissions(
    submissions: list[Submission],
    *,
    json_output: bool,
    title: str,
) -> None:
    if json_output:
        _print_json(submissions)
        return

    table = Table(title=title)
    table.add_column("ID", justify="right")
    table.add_column("Challenge", justify="right")
    table.add_column("Result")
    table.add_column("Provided")
    table.add_column("Date")
    for submission in submissions:
        table.add_row(
            str(submission.id),
            str(submission.challenge_id),
            submission.type or "",
            submission.provided or "",
            submission.date or "",
        )
    console.print(table)
