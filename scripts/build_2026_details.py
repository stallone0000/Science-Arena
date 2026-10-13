#!/usr/bin/env python3
"""Build a thin public detail view from checksum-bound release records in CI."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "scripts/sources/2026"
SELECTED = ("inputs-2026", "runs-table6-ipho-icho", "runs-table6-nbpho-usapho")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def download(row, directory, release):
    path = directory / row["filename"]
    url = f'https://github.com/{release["repository"]}/releases/download/{release["tag"]}/{row["filename"]}'
    for attempt in range(3):
        try:
            digest = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=90) as source, path.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
            require(path.stat().st_size == row["bytes"], "Archive size mismatch")
            require(digest.hexdigest() == row["sha256"], "Archive checksum mismatch")
            print(f'Verified archive {row["filename"]} ({row["bytes"]} bytes)', flush=True)
            return path
        except Exception:
            path.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def archive_members(path):
    import zstandard
    if path.suffix == ".zip":
        class ZipAdapter:
            def __init__(self, archive):
                self.archive = archive

            def extractfile(self, member):
                return self.archive.open(member.info)

        class ZipMember:
            def __init__(self, info):
                self.info = info
                self.size = info.file_size
                self.linkname = ""

            def isfile(self):
                return not self.info.is_dir()

            def issym(self):
                return False

            def islnk(self):
                return False

        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                name = str(PurePosixPath(member.filename))
                require(not name.startswith("/") and ".." not in PurePosixPath(name).parts, "Unsafe ZIP path")
                yield ZipAdapter(archive), ZipMember(member), name
        return
    with path.open("rb") as source, zstandard.ZstdDecompressor().stream_reader(source) as stream:
        with tarfile.open(fileobj=stream, mode="r|") as archive:
            for member in archive:
                name = str(PurePosixPath(member.name))
                require(not name.startswith("/") and ".." not in PurePosixPath(name).parts, "Unsafe archive path")
                yield archive, member, name


def inspect(paths, analysis):
    results = {}
    for path in paths:
        if path.name.endswith(".json.zst"):
            import zstandard
            with path.open("rb") as handle, zstandard.ZstdDecompressor().stream_reader(handle) as stream:
                obj = json.load(stream)
            results[path.name] = {"json_keys": list(obj) if isinstance(obj, dict) else [], "matched_sealed_records": {}, "samples": {}, "roots": {}}
            continue
        roots = Counter()
        links = {}
        matches = {s["competition_key"]: {"solver": 0, "judge": 0, "items": False} for s in analysis["sources"]}
        samples = {}
        for archive, member, name in archive_members(path):
            if member.issym() or member.islnk():
                links[name] = member.linkname
            if not member.isfile():
                continue
            roots["/".join(name.split("/")[:4])] += 1
            for spec in analysis["sources"]:
                contest = spec["competition_key"]
                if name == spec["items_path"]:
                    data = archive.extractfile(member).read()
                    require(hashlib.sha256(data).hexdigest() == spec["items_sha256"], "Frozen items mismatch")
                    matches[contest]["items"] = True
                for stage in ("solver", "judge"):
                    if name.startswith(spec["run_root"] + "/" + stage + "/") and name.endswith(".json") and "-attempts/" not in name:
                        matches[contest][stage] += 1
                        key = contest + "/" + stage
                        if key not in samples:
                            obj = json.load(archive.extractfile(member))
                            samples[key] = {"path": name, "keys": list(obj), "fields": {k: obj[k] for k in ("terminal", "status", "route", "solver_route", "item_id", "score", "max_score") if k in obj}, "parsed_keys": list(obj.get("parsed") or {})}
        results[path.name] = {"roots": dict(roots), "links": links, "matched_sealed_records": matches, "samples": samples}
    print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    release = read(SOURCES / "release_assets.json")
    analysis = read(SOURCES / "analysis_manifest.json")
    rows = [row for row in release["assets"] if args.inspect or row["name"] in SELECTED]
    with tempfile.TemporaryDirectory(prefix="science-arena-release-") as temporary:
        with ThreadPoolExecutor(max_workers=3) as pool:
            paths = list(pool.map(lambda row: download(row, Path(temporary), release), rows))
        if args.inspect:
            inspect(paths, analysis)
        else:
            raise RuntimeError("Detail build must be enabled after the source inventory is verified")


if __name__ == "__main__":
    main()
