"""Catalog (payloads.json + payloads_v2.json) and separately published, content-addressed icons.

pldmgr catalog format: https://github.com/itsPLK/ps5-payload-manager/blob/main/CUSTOM_REPOSITORIES.md
"""
import base64
import hashlib
import html
import json
import os
import re
import tempfile
from colorsys import hls_to_rgb
from pathlib import Path
from zlib import crc32

CATALOG = Path('payloads.json')  # object wrapper with icons_url (a bare array would show no icons)
CATALOG_V2 = Path('payloads_v2.json')  # identical copy; pldmgr's default source URL scheme tries this first
ICONS = Path('icons.json')
JSON_FILE = str(CATALOG)
CATALOG_NAME = 'PS5 Payloads Mirror'
MAX_RELEASE_NOTES_BYTES = 2047  # pldmgr backend limit
MAX_ICON_CHARS = 12288  # pldmgr limit per data URI
MAX_KEY_BYTES = 127
ICON_PREFIXES = ('data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/svg+xml;base64,')

# pldmgr fields first, then our own bookkeeping fields (ignored by pldmgr).
FIELD_ORDER = [
    'id', 'name', 'filename', 'url', 'source', 'source_direct', 'asset_pattern', 'prerelease',
    'extract_file', 'description', 'author', 'last_update', 'version', 'category', 'checksum',
    'icon_key', 'details_url', 'release_notes',
]


def atomic_json(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_catalog():
    target = CATALOG if CATALOG.exists() else CATALOG_V2
    if not target.exists():
        return []
    with open(target, encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get('payloads', [])
    return data


def reorder_item(item):
    ordered = {k: item[k] for k in FIELD_ORDER if k in item}
    ordered.update({k: v for k, v in item.items() if k not in ordered})
    return ordered


def save_catalog(payloads):
    # Both files carry icons_url: users may have added either URL as a source, and a bare
    # array has no way to reference icons.
    catalog = {
        'name': CATALOG_NAME,
        'icons_url': ICONS.name,
        'payloads': payloads,
    }
    atomic_json(CATALOG, catalog)
    atomic_json(CATALOG_V2, catalog)


def load_icons():
    if not ICONS.exists():
        return {}
    return json.loads(ICONS.read_text(encoding='utf-8'))['icons']


def payload_icon(payload):
    return load_icons().get(payload.get('icon_key'))


def check_icon(data):
    if not data.startswith(ICON_PREFIXES) or len(data) > MAX_ICON_CHARS:
        raise ValueError('Expected a bounded base64 PNG, JPEG or SVG icon')
    if not base64.b64decode(data.split(',', 1)[1], validate=True):
        raise ValueError('Empty icon data')


def assign_icon(payload, data):
    check_icon(data)
    key = hashlib.sha256(data.encode('ascii')).hexdigest()
    icons = load_icons()
    icons[key] = data
    # Publish image data before publishing catalog references to it.
    atomic_json(ICONS, {'icons': icons})
    payload.pop('icon', None)
    payload['icon_key'] = key


def prune_icons(payloads):
    """Drop icons no payload references (icon catalog is capped at 4096 keys / 4 MiB)."""
    icons = load_icons()
    used = {p.get('icon_key') for p in payloads}
    kept = {k: v for k, v in icons.items() if k in used}
    if kept != icons:
        atomic_json(ICONS, {'icons': kept})
    return len(icons) - len(kept)


def slug(name):
    return re.sub(r'[^a-z0-9._-]+', '-', name.lower()).strip('-')


def truncate_utf8(text, limit=MAX_RELEASE_NOTES_BYTES):
    """Truncate to `limit` bytes without splitting a character; add an ellipsis when cut."""
    text = (text or '').replace('\r\n', '\n').strip()
    raw = text.encode('utf-8')
    if len(raw) <= limit:
        return text
    ellipsis = '…'.encode()
    cut = raw[: limit - len(ellipsis)].decode('utf-8', errors='ignore')
    return cut.rstrip() + '…'


def ensure_metadata(item):
    """Stable id, kept across versions so favorites/autoload survive updates."""
    item.setdefault('id', slug(item['name']))


def _initials(name):
    words = [w for w in re.split(r'[^A-Za-z0-9]+', re.sub(r'([a-z])([A-Z])', r'\1 \2', name)) if w]
    if len(words) >= 2:
        return ''.join(w[0] for w in words[:3]).upper()
    return (words[0][:2] if words else '?').capitalize()


def make_icon(name):
    """Deterministic 128x128 monogram SVG data URI; fallback when no real icon is found."""
    hue = (crc32(name.encode()) % 360) / 360
    r, g, b = (round(c * 255) for c in hls_to_rgb(hue, 0.42, 0.55))
    fill = f'#{r:02x}{g:02x}{b:02x}'
    text = html.escape(_initials(name))
    size = 52 if len(text) <= 2 else 40
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128'>"
        f"<rect width='128' height='128' rx='24' fill='{fill}'/>"
        f"<text x='64' y='{64 + size * 0.35:.0f}' font-family='Arial,sans-serif' font-size='{size}' "
        f"font-weight='bold' fill='#fff' text-anchor='middle'>{text}</text></svg>"
    )
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()
