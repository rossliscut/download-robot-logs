"""Command line for download-robot-logs."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from download_robot_logs.download import download_package
from download_robot_logs.m4 import M4_PORT, M4_TYPES, download_m4, parse_m4_types
from download_robot_logs.select import TIME_FMT, parse_last


def _parse_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, TIME_FMT)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"use {TIME_FMT}, got {value}") from exc


def _parse_last(value: str) -> timedelta:
    try:
        return parse_last(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _parse_types(value: str) -> list[str]:
    try:
        return parse_m4_types(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download a SEER Robokit, RDSCore, or M4 debug package."
    )
    parser.add_argument("--host", required=True, help="Robot or M4 IP")
    parser.add_argument(
        "--port",
        type=int,
        help=f"M4 HTTP port (default {M4_PORT}). Robokit and RDS use 19208 when this is omitted.",
    )
    parser.add_argument("--start", type=_parse_time, help="Window start, yyyy-MM-dd HH:MM:SS")
    parser.add_argument("--end", type=_parse_time, help="Window end, yyyy-MM-dd HH:MM:SS")
    parser.add_argument(
        "--last",
        "--Last",
        type=_parse_last,
        help="Duration before the robot clock, such as 10m, 1h, or 90s. A bare number is minutes.",
    )
    parser.add_argument("--rds", action="store_true", help="Download an RDSCore debug package instead of Robokit")
    parser.add_argument("--m4", action="store_true", help="Download an M4 log zip over HTTP")
    parser.add_argument(
        "--types",
        type=_parse_types,
        help="M4 log categories, comma-separated. Default: " + ", ".join(M4_TYPES),
    )
    parser.add_argument("--user", help="M4 sign-in username")
    parser.add_argument("--password", help="M4 sign-in password")
    parser.add_argument(
        "--output",
        type=Path,
        help="Zip path or directory. M4 defaults to the file name returned by the server.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.last is not None and (args.start is not None or args.end is not None):
        print("--last replaces --start and --end", file=sys.stderr)
        return 2
    if (args.start is None) != (args.end is None):
        print("pass both --start and --end, or neither", file=sys.stderr)
        return 2
    if args.m4 and args.rds:
        print("--m4 replaces --rds", file=sys.stderr)
        return 2
    if (args.user is None) != (args.password is None):
        print("pass both --user and --password, or neither", file=sys.stderr)
        return 2
    if (args.user is not None or args.types is not None) and not args.m4:
        print("pass --user, --password, and --types with --m4", file=sys.stderr)
        return 2
    if args.m4 and args.last is None and args.start is None:
        print("pass --last or --start and --end", file=sys.stderr)
        return 2
    port = args.port if args.port is not None else (M4_PORT if args.m4 else 19208)
    if args.m4:
        try:
            path = download_m4(
                args.host,
                port,
                args.output,
                args.start,
                args.end,
                args.last,
                args.types or list(M4_TYPES),
                args.user,
                args.password,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(path)
        return 0
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    prefix = "RDSCore-Debug" if args.rds else "robokit-Debug"
    output = args.output or Path(f"{prefix}-{stamp}.zip")
    if output.suffix.lower() != ".zip":
        output = output / f"{prefix}-{stamp}.zip"
    try:
        path, failed = download_package(
            args.host, port, output, args.start, args.end, args.last, args.rds
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
