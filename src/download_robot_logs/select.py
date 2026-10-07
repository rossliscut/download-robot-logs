"""Zip layout, time window, and map selection."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

RBK = "/usr/local/etc/.SeerRobotics/rbk/resources/"
LOG_DIR = "/usr/local/etc/.SeerRobotics/rbk/diagnosis/log"
RDS_CORE_LOG = "/opt/.data/rdscore/diagnosis/log"
RDS_APP_LOGS = "/opt/.data/rds/logs"
RDS_MODELS = "/opt/.data/rdscore/resources/models/"
RHCR_PARENTS = [
    RDS_CORE_LOG,
    "/opt/data/rdscore/diagnosis/log",
]
PAT_DIRS = [
    LOG_DIR + "/patlogs",
    RBK + "patlogs",
]
STAMP = re.compile(r"(20\d{2})-(\d{2})-(\d{2})[_-](\d{2})-(\d{2})-(\d{2})")
SMAP144 = re.compile(r"\[smap\]\[144\|([^\]|]+)")
CURRENT = re.compile(r"_currentMap\|([^\s|\]]+)")
SUCCESS = re.compile(r"\[smap\]\[644\|(\S+) success")
MAP_PATH = re.compile(r"/maps/(?:tmp/)?([^/\s|\]\"']+)")
CHASSIS = re.compile(r"\[Chassis Info:\s*(\{.*\})\]\s*$")
TIME_FMT = "%Y-%m-%d %H:%M:%S"
ROBOT_CLOCK = re.compile(r"(20\d{2})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})")
_LAST = re.compile(
    r"^(\d+(?:\.\d+)?)(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hour|hours|d|day|days)?$",
    re.IGNORECASE,
)
_HMS = re.compile(r"^(\d+):(\d{2}):(\d{2})$")


def parse_stamp(name: str) -> datetime | None:
    match = STAMP.search(name)
    if not match:
        return None
    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    return datetime(year, month, day, hour, minute, second)


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FMT)


def parse_robot_datetime(text: str) -> datetime | None:
    """Robot local time from 15117 dateTime, ignoring the millisecond tail."""
    match = ROBOT_CLOCK.search(text)
    if not match:
        return None
    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    return datetime(year, month, day, hour, minute, second)


def parse_last(value: str) -> timedelta:
    """Duration for --last. A bare number is minutes."""
    text = value.strip()
    clock = _HMS.fullmatch(text)
    if clock:
        hours, minutes, seconds = (int(part) for part in clock.groups())
        span = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    else:
        match = _LAST.fullmatch(text)
        if not match:
            raise ValueError(f"use 10m, 1h, 90s, or 0:10:00, got {value}")
        amount = float(match.group(1))
        unit = (match.group(2) or "m").lower()
        if unit in {"m", "min", "mins", "minute", "minutes"}:
            span = timedelta(minutes=amount)
        elif unit in {"s", "sec", "secs", "second", "seconds"}:
            span = timedelta(seconds=amount)
        elif unit in {"h", "hr", "hour", "hours"}:
            span = timedelta(hours=amount)
        else:
            span = timedelta(days=amount)
    if span.total_seconds() <= 0:
        raise ValueError("duration must be positive")
    return span


def to_zip_rel(full: str) -> str | None:
    full = full.replace("\\", "/")
    if "/patlogs/" in full and full.endswith(".pat"):
        return "log/patlogs/" + full.rsplit("/", 1)[-1]
    if full.startswith(RBK):
        return full[len(RBK) :]
    if "/diagnosis/log/robod/log/" in full:
        return "log/" + full.rsplit("/", 1)[-1]
    if "/diagnosis/log/" in full:
        return "log/" + full.split("/diagnosis/log/", 1)[1]
    if full.startswith("/var/log/"):
        return "log/" + full.rsplit("/", 1)[-1]
    if "/robod/appInfo/log/" in full:
        return "log/" + full.rsplit("/", 1)[-1]
    if "/robod/appInfo/backupFile/" in full:
        return "backupFile/" + full.rsplit("/", 1)[-1]
    return None


def to_rds_zip_rel(full: str) -> str | None:
    """Zip path for an RDSCore debug package. config/ is flattened to the file name."""
    full = full.replace("\\", "/")
    name = full.rsplit("/", 1)[-1]
    if not name or name.startswith("Roboshop_"):
        return None
    if full.startswith("/opt/data/rds/config/"):
        return "config/" + name
    if full.startswith("/opt/data/rds/script/"):
        return "script/" + name
    if full.startswith("/opt/data/rds/history/task/"):
        return "task/" + name
    if full.startswith(RDS_APP_LOGS + "/"):
        return "logs/" + name
    if "/diagnosis/log/rhcr/" in full:
        return "rhcr/" + name
    if "/diagnosis/log/" in full:
        return "log/" + name
    if full.startswith("/opt/.data/rdscore/resources/params/"):
        return "params/" + name
    if full.startswith("/opt/.data/rdscore/resources/scene/"):
        return "scene/" + name
    if full.startswith(RDS_MODELS):
        return "models/" + full[len(RDS_MODELS) :]
    if full.startswith("/opt/.data/rdscore/resources/runtimes/"):
        return "runtimes/" + name
    if full.startswith("/opt/.data/rdscore/resources/db/"):
        return "db/" + name
    if full.startswith("/var/log/"):
        return "log/" + name
    if "/robod/appInfo/log/" in full:
        return "log/" + name
    return None


def listed_rhcr(paths: list[str]) -> bool:
    """True when 5130 already named an rhcr log or its directory."""
    for path in paths:
        full = path.replace("\\", "/")
        name = full.rsplit("/", 1)[-1]
        if "/rhcr/" in full or name.startswith("rhcr_"):
            return True
    return False


def rhcr_dir_from_listing(parent: str, items: list[dict]) -> str | None:
    """Directory path for a child named rhcr. Prefer file_path from 5100."""
    parent = parent.replace("\\", "/").rstrip("/")
    for item in items:
        if not item.get("is_dir") or str(item.get("name") or "") != "rhcr":
            continue
        raw = str(item.get("file_path") or "").replace("\\", "/").rstrip("/")
        if raw.startswith("/"):
            return raw
        return parent + "/rhcr"
    return None


def rhcr_log_names(items: list[dict]) -> list[str]:
    names: list[str] = []
    for item in items:
        if item.get("is_dir"):
            continue
        name = str(item.get("name") or "")
        if name.startswith("rhcr_") and name.endswith((".log", ".log.gz")):
            names.append(name)
    return names


def is_robokit_main(name: str) -> bool:
    return (
        name.startswith("robokit_")
        and not name.startswith(("robokit_warning_", "robokit_error_"))
        and name.endswith(".log")
    )


def listed_robokit(paths: list[str]) -> bool:
    """True when 5130 already named a main robokit_*.log in the log directory."""
    prefix = LOG_DIR + "/"
    for path in paths:
        full = path.replace("\\", "/")
        if full.startswith(prefix) and "/" not in full[len(prefix) :] and is_robokit_main(full[len(prefix) :]):
            return True
    return False


def robokit_log_names(items: list[dict]) -> list[str]:
    return [
        str(item.get("name") or "")
        for item in items
        if not item.get("is_dir") and is_robokit_main(str(item.get("name") or ""))
    ]


def series_key(rel: str) -> str | None:
    name = rel.rsplit("/", 1)[-1]
    if rel.startswith("log/patlogs/") and name.endswith(".pat"):
        return "pat"
    if rel.startswith("log/trace/"):
        return "trace"
    if rel.startswith("log/d/"):
        return "d"
    if rel.startswith("log/warning/"):
        return "warning"
    if rel.startswith("log/error/"):
        return "error"
    if rel.startswith("logs/") and name.startswith("Rds_") and name.endswith(".log"):
        return "rds"
    if rel.startswith("rhcr/") and name.startswith("rhcr_"):
        return "rhcr"
    if rel.count("/") == 1 and name.startswith("rdscore_") and name.endswith((".log", ".log.gz")):
        return "rdscore"
    if rel.count("/") == 1 and name.startswith("RobodPro_"):
        return "robod"
    if rel.count("/") == 1 and is_robokit_main(name):
        return "robokit"
    return None


def filter_rotated(
    rels: list[str],
    window_start: datetime,
    window_end: datetime,
    download_time: datetime,
) -> list[str]:
    """Keep rotated logs that cover the package window.

    A file's segment runs from the timestamp in its name until the next file
    in the same series, or until download_time when it is the newest. The
    previous segment is skipped when it only sticks into the window for under
    a minute. That avoids downloading an overnight patlog that closed a few
    seconds after the new robokit log started.
    """
    grouped: dict[str, list[tuple[datetime, str]]] = {}
    kept: list[str] = []
    for rel in rels:
        start = parse_stamp(rel)
        key = series_key(rel)
        if start is None or key is None:
            kept.append(rel)
            continue
        grouped.setdefault(key, []).append((start, rel))
    for group in grouped.values():
        group.sort()
        for index, (start, rel) in enumerate(group):
            end = group[index + 1][0] if index + 1 < len(group) else download_time
            if end <= window_start or start >= window_end:
                continue
            if start < window_start and (end - window_start) < timedelta(minutes=1):
                continue
            kept.append(rel)
    return kept


def chassis_map_stems(text: str) -> set[str]:
    """Map in use, the way RoboCare reads it.

    RoboCare takes CURRENT_MAP from each [Chassis Info: {...}] JSON, then
    debug:current_map when that is empty. The value is the stem without .smap.
    Robokit writes the line about every 33 seconds whether or not the map
    was reloaded.
    """
    stems: set[str] = set()
    for line in text.splitlines():
        if "Chassis Info" not in line:
            continue
        match = CHASSIS.search(line)
        if not match:
            continue
        try:
            data = json.loads(match.group(1), strict=False)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        name = data.get("CURRENT_MAP") or data.get("debug:current_map")
        if isinstance(name, str) and name:
            stems.add(name)
    return stems


def loaded_map_stems(text: str) -> set[str]:
    stems: set[str] = set()
    for line in text.splitlines():
        if "[addMapMD5]" in line or "uploadMap" in line:
            continue
        blobs = SMAP144.findall(line) + CURRENT.findall(line) + SUCCESS.findall(line)
        blobs += MAP_PATH.findall(line)
        for raw in blobs:
            name = raw.strip().rsplit("/", 1)[-1]
            for suffix in (".smap", ".2dlh"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            else:
                if "." in name:
                    continue
            if name and name not in {"0", "tmp"}:
                stems.add(name)
    return stems


def map_wanted(filename: str, stems: set[str]) -> bool:
    return any(filename == f"{stem}.smap" or filename == f"{stem}.2dlh" or filename.startswith(stem + ".") for stem in stems)
