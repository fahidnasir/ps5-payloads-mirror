# ps5-payloads-mirror

Mirrors latest release binaries from various PS5 homebrew payload repos into one
GitHub Release (`payloads-mirror` tag) on this repo, with `payloads.json` as
metadata index and `README.md` table auto-generated from it.

## Files

- `payloads.json` — source of truth. List of payload entries (name, filename, url,
  source, source_direct, version, category, checksum, etc).
- `update_payloads.py` — runs on schedule. For each entry with a `source`, checks
  upstream latest GitHub/Gitea release, downloads new asset if version changed,
  re-uploads to `payloads-mirror` release, updates `payloads.json`, regenerates
  README table, deletes stale release assets (recording download stats first).
- `add_payload.py` — interactive CLI to add a new payload entry (prompts for URL,
  description, category; auto-detects latest release asset).
- `download_stats.json` — download counts of removed/stale assets, recorded before
  deletion.
- `.github/workflows/update_mirror.yml` — cron job, daily 00:00 UTC + manual dispatch.

## How update flow works (update_payloads.py)

1. Load `payloads.json`.
2. For each item with `source` url: parse domain/owner/repo, fetch latest release
   via `gh api` (github.com) or Gitea API (other domains, e.g. git.etawen.dev).
3. Score release assets (prefers `.elf`/`.bin` matching, `ps5` in name, penalizes
   `ps4`/`install`; `asset_pattern` regex can pin exact asset when repo has multiple).
4. If zip asset: download to temp, extract `extract_file` (or auto-detect single
   `.elf` inside), else download directly.
5. Rename to `{name}_{version}.{ext}`, compute sha256 checksum, update item fields,
   set `url` to mirror's release download URL.
8. Sort payloads by `last_update` desc, rewrite `payloads.json`, regenerate README
   table between `<!-- PAYLOADS_START -->` / `<!-- PAYLOADS_END -->` markers.
9. Cleanup: delete release assets not referenced by any current `filename`, log
   their download_count + deletion date into `download_stats.json`.

Special case: `ps5debug`/no-`source` items skip version-check, just get url pointed
at mirror if not already.

## How to add a new repo to track

Two ways:

1. **Interactive**: `python add_payload.py` — paste GitHub download URL, pick/add
   category, script fetches latest release, downloads, appends entry to
   `payloads.json`, updates README. Refuses duplicate `source`.
2. **Manual**: append object to `payloads.json` with at least `source` (repo
   releases URL, e.g. `https://github.com/OWNER/REPO/releases`) and `name`. Leave
   `version`/`filename` unset — next `update_payloads.py` run will populate them.
   Optional: `asset_pattern` (regex to disambiguate multi-asset releases),
   `extract_file` (path inside zip to pull the .elf from), `category`.

Either way, next scheduled/manual workflow run picks it up and does the actual
download + mirror + release upload.

## Automation (GitHub Actions, free)

`.github/workflows/update_mirror.yml`:
- Trigger: `cron: '0 0 * * *'` (daily midnight UTC) + `workflow_dispatch` (manual
  button in Actions tab).
- Runs `update_payloads.py`, creates/reuses `payloads-mirror` release, uploads
  changed payload binaries with `gh release upload --clobber`, commits
  `payloads.json`/`README.md`/`download_stats.json` back with
  `github-actions[bot]` identity, pushes.
- Uses default `GITHUB_TOKEN` (no PAT/secrets setup needed) — free on public repo
  standard GitHub-hosted runners.

To change check frequency: edit the cron expression. To test without waiting:
Actions tab → this workflow → "Run workflow" (workflow_dispatch).

## Gotchas

- Non-github.com sources (Gitea, e.g. git.etawen.dev) use a different API path
  (`/api/v1/repos/...`) — same shape response assumed (`tag_name`,
  `published_at`, `assets[].browser_download_url`).
- `BASE_URL` and owner/repo ("itsPLK/ps5-payloads-mirror") are hardcoded in both
  scripts — update if repo ever moves/forks.
- Asset scoring can silently pick wrong asset for repos with many release files;
  use `asset_pattern` to pin it down (see `zftpd` entry using `"zhttp"`).
