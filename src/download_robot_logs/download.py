"""Download a Roboshop-style debug package."""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from download_robot_logs.client import RobodClient
from download_robot_logs.select import (
    LOG_DIR,
    PAT_DIRS,
    filter_rotated,
    format_time,
    loaded_map_stems,
    map_wanted,
    parse_stamp,
    to_zip_rel,
)


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _is_map_source(rel: str) -> bool:
    """Plain logs that name the map in use, including a segment that did not reload it."""
    name = rel.rsplit("/", 1)[-1]
    if not name.endswith(".log"):
        return False
    if rel.count("/") == 1 and name.startswith("robokit_") and not name.startswith(
        ("robokit_warning_", "robokit_error_")
    ):
        return True
    return rel.startswith(("log/warning/", "log/error/"))


def _json_call(client: RobodClient, api: int, body: dict, timeout: float) -> tuple[int, bytes]:
    payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return client.call(api, payload, timeout)


def list_dir(client: RobodClient, directory: str) -> list[dict]:
    try:
        api, blob = _json_call(client, 5100, {"path": directory}, 30)
    except OSError as exc:
        _log(f"5100 fail {directory} {exc}")
        return []
    if api != 15100 or not blob:
        _log(f"5100 api={api} bytes={len(blob)} {directory}")
        return []
    try:
        data = json.loads(blob.decode("utf-8"))
    except json.JSONDecodeError:
        _log(f"5100 not json {directory}")
        return []
    return list(data.get("file_list") or [])


def newest_robokit_start(client: RobodClient) -> datetime | None:
    names = [
        str(item.get("name") or "")
        for item in list_dir(client, LOG_DIR)
        if not item.get("is_dir")
    ]
    stamps = []
    for name in names:
        if not (name.startswith("robokit_") and name.endswith(".log")):
            continue
        if name.startswith(("robokit_warning_", "robokit_error_")):
            continue
        stamp = parse_stamp(name)
        if stamp is not None:
            stamps.append(stamp)
    return max(stamps) if stamps else None


def list_5130(client: RobodClient, start: datetime, end: datetime) -> list[str]:
    api, blob = _json_call(
        client,
        5130,
        {"startTime": format_time(start), "endTime": format_time(end)},
        60,
    )
    _log(f"5130 api={api} bytes={len(blob)} {format_time(start)} -> {format_time(end)}")
    data = json.loads(blob.decode("utf-8"))
    seen: set[str] = set()
    paths: list[str] = []
    for group in data.get("fileList") or []:
        for full in group.get("filePaths") or []:
            full = str(full).replace("\\", "/")
            if full not in seen:
                seen.add(full)
                paths.append(full)
    _log(f"unique paths {len(paths)}")
    return paths


def extra_pats(client: RobodClient, paths: list[str]) -> list[str]:
    if any("/patlogs/" in path or path.endswith(".pat") for path in paths):
        _log("patlog already in 5130")
        return []
    _log("5130 has no patlog, listing directory")
    for directory in PAT_DIRS:
        items = list_dir(client, directory)
        names = [
            str(item.get("name") or "")
            for item in items
            if not item.get("is_dir") and str(item.get("name") or "").endswith(".pat")
        ]
        if not names:
            continue
        _log(f"pat files {directory}: {len(names)}")
        return [f"{directory}/{name}" for name in names]
    _log("no patlog directory")
    return []


def jobs_from_paths(paths: list[str]) -> list[tuple[str, str]]:
    jobs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for full in paths:
        rel = to_zip_rel(full)
        if not rel or rel.startswith("log/Roboshop_") or rel in seen:
            continue
        seen.add(rel)
        jobs.append((rel, full))
    return jobs


def download_file(client: RobodClient, full: str, dest: Path) -> int:
    parent, name = full.rsplit("/", 1)
    timeout = 300.0 if name.endswith((".2dlh", ".pcd", ".smap", ".pat", ".zst")) else 120.0
    _api, blob = _json_call(client, 5101, {"path": parent, "file_name": name}, timeout)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)
    return len(blob)


def run_batch(
    client: RobodClient,
    root: Path,
    batch: list[tuple[str, str]],
    label: str,
    failed: list[str],
) -> None:
    for index, (rel, full) in enumerate(batch, 1):
        dest = root / rel
        try:
            size = download_file(client, full, dest)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{rel} {exc}")
            _log(f"{label} {index}/{len(batch)} FAIL {rel} {exc}")
            continue
        _log(f"{label} {index}/{len(batch)} {size:10d} {rel}")


def write_zip(root: Path, dest: Path) -> int:
    files = [path for path in root.rglob("*") if path.is_file()]
    dirs = {path.parent.relative_to(root).as_posix() for path in files}
    dirs.discard(".")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True
    ) as archive:
        for directory in sorted(dirs):
            if directory:
                archive.writestr(directory + "/", b"")
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    return len(files)


def download_package(
    host: str,
    port: int,
    output: Path,
    start: datetime | None,
    end: datetime | None,
) -> tuple[Path, int]:
    download_time = datetime.now().replace(microsecond=0)
    window_end = end or download_time
    client = RobodClient(host, port)
    failed: list[str] = []
    try:
        window_start = start or newest_robokit_start(client)
        if window_start is None:
            raise RuntimeError("no robokit_*.log found; pass --start and --end")
        if window_start >= window_end:
            raise RuntimeError(f"empty window {format_time(window_start)} -> {format_time(window_end)}")
        paths = list_5130(client, window_start, window_end)
        paths.extend(extra_pats(client, paths))
        jobs = jobs_from_paths(paths)
        rels = [rel for rel, _full in jobs]
        allowed = set(filter_rotated(rels, window_start, window_end, download_time))
        jobs = [(rel, full) for rel, full in jobs if rel in allowed]
        robokit = [item for item in jobs if _is_map_source(item[0])]
        maps = [item for item in jobs if item[0].startswith("maps/")]
        rest = [item for item in jobs if item not in robokit and item not in maps]
        _log(f"window {format_time(window_start)} -> {format_time(window_end)}")
        _log(f"jobs robokit={len(robokit)} maps={len(maps)} other={len(rest)}")
        root = output.parent / (output.stem + "-files")
        root.mkdir(parents=True, exist_ok=True)
        run_batch(client, root, robokit, "log", failed)
        stems: set[str] = set()
        for rel, _full in robokit:
            path = root / rel
            if path.is_file():
                stems |= loaded_map_stems(path.read_text(encoding="utf-8", errors="replace"))
        _log("loaded maps " + (", ".join(sorted(stems)) if stems else "(none)"))
        if stems:
            chosen = [item for item in maps if map_wanted(item[0].rsplit("/", 1)[-1], stems)]
            _log(f"maps keep {len(chosen)} skip {len(maps) - len(chosen)}")
            run_batch(client, root, chosen, "map", failed)
        else:
            _log("no current map named in robokit, warning, or error logs; skip maps/")
        run_batch(client, root, rest, "file", failed)
        count = write_zip(root, output)
    finally:
        client.close()
    _log(f"DONE failed={len(failed)} files={count} zip={output}")
    for item in failed:
        _log(f"FAILED {item}")
    return output, len(failed)
