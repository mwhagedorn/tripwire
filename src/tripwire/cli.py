"""Command-line entry point for tripwire."""

import argparse
import asyncio
import sys
from pathlib import Path

from . import baseline, reporting
from .eero_adapter import AdapterError, AuthenticationError, EeroAdapter, EeroClientAdapter
from .scanner import Comparison, Scanner, Snapshot


def _not_implemented(args: argparse.Namespace) -> int:
    print(f"tripwire {args.command}: not implemented yet", file=sys.stderr)
    return 1


def _session_path() -> Path:
    path = Path.home() / ".tripwire" / "session"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def _request_code(adapter: EeroAdapter, identifier: str) -> bool:
    async with adapter:
        return await adapter.login(identifier)


def _login(args: argparse.Namespace) -> int:
    adapter = EeroClientAdapter(cookie_file=str(_session_path()))
    try:
        asyncio.run(_request_code(adapter, args.identifier))
    except AdapterError as exc:
        print(f"tripwire login: failed to request a verification code: {exc}", file=sys.stderr)
        return 1
    print("Verification code requested. Run `tripwire verify <code>` with the code you received.")
    return 0


async def _confirm_code(adapter: EeroAdapter, code: str) -> bool:
    async with adapter:
        return await adapter.verify(code)


def _verify(args: argparse.Namespace) -> int:
    session_path = _session_path()
    adapter = EeroClientAdapter(cookie_file=str(session_path))
    try:
        verified = asyncio.run(_confirm_code(adapter, args.code))
    except AdapterError as exc:
        print(f"tripwire verify: verification failed: {exc}", file=sys.stderr)
        return 1
    if not verified:
        print("tripwire verify: verification failed", file=sys.stderr)
        return 1
    print(f"Logged in. Session stored at {session_path}")
    return 0


async def _end_session(adapter: EeroAdapter) -> bool:
    async with adapter:
        return await adapter.logout()


def _logout(args: argparse.Namespace) -> int:
    session_path = _session_path()
    adapter = EeroClientAdapter(cookie_file=str(session_path))
    try:
        asyncio.run(_end_session(adapter))
    except AdapterError as exc:
        print(f"tripwire logout: failed to revoke the session: {exc}", file=sys.stderr)
        return 1
    print("Logged out. Stored credentials cleared.")
    return 0


async def _capture_baseline(adapter: EeroAdapter, path: Path) -> Snapshot:
    async with adapter:
        if not adapter.is_authenticated:
            raise AuthenticationError("Not logged in. Run `tripwire login` first.")
        return await baseline.capture(Scanner(adapter), path)


def _init(args: argparse.Namespace) -> int:
    path = Path(args.baseline)
    if path.exists() and not args.force:
        print(
            f"tripwire init: {path} already exists. Use --force to overwrite, "
            "or run `tripwire update` to refresh it.",
            file=sys.stderr,
        )
        return 1

    adapter = EeroClientAdapter(cookie_file=str(_session_path()))
    try:
        snapshot = asyncio.run(_capture_baseline(adapter, path))
    except AdapterError as exc:
        print(f"tripwire init: {exc}", file=sys.stderr)
        return 1
    print(f"Baseline created at {path} ({len(snapshot.devices)} devices).")
    return 0


def _update(args: argparse.Namespace) -> int:
    path = Path(args.baseline)
    if not path.exists():
        print(
            f"tripwire update: no baseline found at {path}. Run `tripwire init` first.",
            file=sys.stderr,
        )
        return 1

    adapter = EeroClientAdapter(cookie_file=str(_session_path()))
    try:
        snapshot = asyncio.run(_capture_baseline(adapter, path))
    except AdapterError as exc:
        print(f"tripwire update: {exc}", file=sys.stderr)
        return 1
    print(f"Baseline updated at {path} ({len(snapshot.devices)} devices).")
    return 0


async def _run_check(adapter: EeroAdapter, path: Path) -> Comparison:
    async with adapter:
        if not adapter.is_authenticated:
            raise AuthenticationError("Not logged in. Run `tripwire login` first.")
        return await baseline.evaluate(Scanner(adapter), path)


EXIT_NO_CHANGES = 0
EXIT_CHANGES_FOUND = 1
EXIT_ERROR = 2


def _check(args: argparse.Namespace) -> int:
    path = Path(args.baseline)
    if not path.exists():
        print(
            f"tripwire check: no baseline found at {path}. Run `tripwire init` first.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    adapter = EeroClientAdapter(cookie_file=str(_session_path()))
    try:
        comparison = asyncio.run(_run_check(adapter, path))
    except (AdapterError, baseline.BaselineError) as exc:
        print(f"tripwire check: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if args.json:
        print(reporting.render_json(comparison))
    else:
        print(reporting.render_text(comparison))
    return EXIT_CHANGES_FOUND if reporting.has_changes(comparison) else EXIT_NO_CHANGES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tripwire")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="Request an Eero login verification code")
    login.add_argument("identifier", help="Email address or phone number for the Eero account")
    login.set_defaults(func=_login)

    verify = subparsers.add_parser("verify", help="Complete login with a received verification code")
    verify.add_argument("code", help="Verification code sent to you by Eero")
    verify.set_defaults(func=_verify)

    logout = subparsers.add_parser("logout", help="Revoke and clear the stored Eero session")
    logout.set_defaults(func=_logout)

    init = subparsers.add_parser("init", help="Create a baseline from the current network state")
    init.add_argument("--baseline", required=True)
    init.add_argument("--force", action="store_true", help="Overwrite an existing baseline file")
    init.set_defaults(func=_init)

    check = subparsers.add_parser("check", help="Compare the current network state to a baseline")
    check.add_argument("--baseline", required=True)
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=_check)

    update = subparsers.add_parser("update", help="Update a baseline with the current network state")
    update.add_argument("--baseline", required=True)
    update.set_defaults(func=_update)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
