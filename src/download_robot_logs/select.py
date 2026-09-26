"""Zip layout, time window, and map selection."""

from __future__ import annotations

import re
from datetime import datetime

RBK = "/usr/local/etc/.SeerRobotics/rbk/resources/"
LOG_DIR = "/usr/local/etc/.SeerRobotics/rbk/diagnosis/log"
PAT_DIRS = [
    LOG_DIR + "/patlogs",
    RBK + "patlogs",
]
STAMP = re.compile(r"(20\d{2})-(\d{2})-(\d{2})[_-](\d{2})-(\d{2})-(\d{2})")
SMAP144 = re.compile(r"\[smap\]\[144\|([^\]|]+)")
CURRENT = re.compile(r"_currentMap\|([^\s|\]]+)")
SUCCESS = re.compile(r"\[smap\]\[644\|(\S+) success")
MAP_PATH = re.compile(r"resources/maps/(?:tmp/)?([^/\s|\]]+)")
TIME_FMT = "%Y-%m-%d %H:%M:%S"


def parse_stamp(name: str) -> datetime | None:
    match = STAMP.search(name)
    if not match:
        return None
    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    return datetime(year, month, day, hour, minute, second)


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FMT)


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
    if rel.count("/") == 1 and name.startswith("RobodPro_"):
        return "robod"
    if (
        rel.count("/") == 1
        and name.startswith("robokit_")
        and not name.startswith(("robokit_warning_", "robokit_error_"))
        and name.endswith(".log")
    ):
        return "robokit"
    return None


def filter_rotated(
    rels: list[str],
    window_start: datetime,
    window_end: datetime,
    download_time: datetime,
) -> list[str]:
    """Keep rotated logs whose filename time falls in the package window.

    The previous segment often stays open until a few seconds after the new
    robokit log starts. Treating that as overlap would pull in the whole
    previous file, including overnight patlogs.
    """
    del download_time
    kept: list[str] = []
    for rel in rels:
        if not rel.startswith("log/"):
            kept.append(rel)
            continue
        start = parse_stamp(rel)
        if start is None or series_key(rel) is None:
            kept.append(rel)
            continue
        if window_start <= start < window_end:
            kept.append(rel)
    return kept


def loaded_map_stems(text: str) -> set[str]:
    stems: set[str] = set()
    for line in text.splitlines():
        if "[addMapMD5]" in line:
            continue
        blobs = SMAP144.findall(line) + CURRENT.findall(line) + SUCCESS.findall(line)
        if "[smap]" in line:
            blobs += MAP_PATH.findall(line)
        for raw in blobs:
            name = raw.strip().rsplit("/", 1)[-1]
            for suffix in (".smap", ".2dlh"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            if name and name not in {"0", "tmp"}:
                stems.add(name)
    return stems


def map_wanted(filename: str, stems: set[str]) -> bool:
    return any(filename == f"{stem}.smap" or filename == f"{stem}.2dlh" or filename.startswith(stem + ".") for stem in stems)
