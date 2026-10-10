"""Sanity checks for payloads.json. Exit non-zero on any problem."""
import json
import re
import sys

REQUIRED = ("name", "source", "category")
ALLOWED = {
    "name", "filename", "url", "source", "source_direct", "asset_pattern",
    "prerelease", "extract_file", "description", "last_update", "version",
    "category", "checksum",
}


def validate(payloads):
    errors = []
    if not isinstance(payloads, list):
        return ["payloads.json must be a list"]
    seen = set()
    for i, item in enumerate(payloads):
        label = item.get("name", f"#{i}")
        for key in REQUIRED:
            if key not in item and not (key == "source" and label == "ps5debug"):
                errors.append(f"{label}: missing {key}")
        for key in item:
            if key not in ALLOWED:
                errors.append(f"{label}: unknown field {key}")
        # a stable entry and its prerelease twin may share a source
        for key in ("name", "filename", ("source", bool(item.get("prerelease")))):
            value = item.get(key[0] if isinstance(key, tuple) else key)
            if value is None:
                continue
            ident = (key, value)
            if ident in seen:
                errors.append(f"{label}: duplicate {ident[0]} {value}")
            seen.add(ident)
        pattern = item.get("asset_pattern")
        if pattern:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"{label}: bad asset_pattern: {exc}")
        if "filename" in item and item.get("checksum") is None:
            errors.append(f"{label}: filename without checksum")
    return errors


def main(path="payloads.json"):
    with open(path) as f:
        errors = validate(json.load(f))
    for err in errors:
        print(f"ERROR: {err}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
