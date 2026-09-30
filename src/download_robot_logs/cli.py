"""Command line for download-robot-logs."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from download_robot_logs.download import download_package
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download a SEER Robokit debug package from Robod TCP 19208."
    )
    parser.add_argument("--host", required=True, help="Robot IP")
    parser.add_argument("--port", type=int, default=19208, help="Robod port (default 19208)")
    parser.add_argument("--start", type=_parse_time, help="Window start, yyyy-MM-dd HH:MM:SS")
    parser.add_argument("--end", type=_parse_time, help="Window end, yyyy-MM-dd HH:MM:SS")
    parser.add_argument(
        "--last",
        "--Last",
        type=_parse_last,
        help="Duration before the robot clock, such as 10m, 1h, or 90s. A bare number is minutes.",
    )
    parser.add_argument("--rds", action="store_true", help="Download an RDSCore debug package instead of Robokit")
    parser.add_argument(
        "--output",
        type=Path,
        help="Zip path. Default: ./robokit-Debug-<timestamp>.zip or ./RDSCore-Debug-<timestamp>.zip",
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
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    prefix = "RDSCore-Debug" if args.rds else "robokit-Debug"
    output = args.output or Path(f"{prefix}-{stamp}.zip")
    if output.suffix.lower() != ".zip":
        output = output / f"{prefix}-{stamp}.zip"
    try:
        path, failed = download_package(
            args.host, args.port, output, args.start, args.end, args.last, args.rds
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
