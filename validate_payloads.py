"""Sanity checks for payloads.json. Exit non-zero on any problem."""
import re
import sys

from catalog import MAX_KEY_BYTES, MAX_RELEASE_NOTES_BYTES, check_icon, load_catalog, load_icons

REQUIRED = ("name", "source", "category")
ALLOWED = {
    "name", "filename", "url", "source", "source_direct", "asset_pattern",
    "prerelease", "extract_file", "description", "last_update", "version",
    "category", "checksum", "id", "author", "icon_key", "details_url", "release_notes",
}
ID_RE = re.compile(r"^[a-z0-9._-]+$")


def validate(payloads):
    errors = []
    if not isinstance(payloads, list):
        return ["payloads.json must be a list"]
    seen = set()
    seen_ids = set()
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
        if "id" in item and not ID_RE.match(item["id"]):
            errors.append(f"{label}: bad id {item['id']!r}")
        if "id" in item and ("id", item["id"]) in seen_ids:
            errors.append(f"{label}: duplicate id {item['id']}")
        seen_ids.add(("id", item.get("id")))
        if len(item.get("icon_key", "").encode()) > MAX_KEY_BYTES:
            errors.append(f"{label}: icon_key too long")
        if len(item.get("release_notes", "").encode()) > MAX_RELEASE_NOTES_BYTES:
            errors.append(f"{label}: release_notes too long")
        pattern = item.get("asset_pattern")
        if pattern:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"{label}: bad asset_pattern: {exc}")
        if "filename" in item and item.get("checksum") is None:
            errors.append(f"{label}: filename without checksum")
    return errors


def validate_icons(payloads):
    icons = load_icons()
    errors = []
    for item in payloads:
        key = item.get("icon_key")
        if not key:
            errors.append(f"{item.get('name')}: missing icon_key")
        elif key not in icons:
            errors.append(f"{item.get('name')}: icon_key {key} not in icons.json")
    for key, uri in icons.items():
        try:
            check_icon(uri)
        except ValueError as exc:
            errors.append(f"icon {key}: {exc}")
    return errors


def main():
    payloads = load_catalog()
    errors = validate(payloads) + validate_icons(payloads)
    for err in errors:
        print(f"ERROR: {err}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
