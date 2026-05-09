"""DAIMON card-art variant management.

Single source of truth for the per-card variant manifest. Used by:
  - migration script (one-shot move of base.png into variants/v0.png)
  - /opt/agents/scripts/daimon_card_art_pass.py (writes new variants)
  - /opt/leeroy-web/backend/app/routes/cards.py (reads manifests for the
    Cards tab, mutates them on canonical/discard actions)

Disk layout (per card):
    art/v1_alpha/<card_id>/
      manifest.json         ← this module is the read/write authority
      base.png              ← MIRROR of canonical variant for legacy callers
      variants/
        v0.png              ← original (the migration target)
        v1.png, v2.png, …   ← later re-rolls

Public preview mirror (served unauth at /api/chat/card-art/<id>/<variant>.png):
    /opt/leeroy-web/uploads/cards/<card_id>/
      base.png, v0.png, v1.png, …   ← `publish_variant` keeps these in sync

Manifest schema:
    {
      "card_id":   "abyss_warden",
      "canonical": "v0",                       # null if no variant promoted
      "variants": [
        {
          "id":           "v0",                # Vn, sequential, never reused
          "seed":         33145,               # NovelAI seed used
          "seed_offset":  0,                   # offset added to deterministic_seed
          "created_at":   "2026-04-23T22:41:00Z",
          "status":       "active",            # active | discarded | pending
          "model":        "nai-diffusion-4-5-full",
          "prompt_version": "miura_v1",        # free-form tag for the recipe
          # ---- skin metadata (optional; absent on base variants) ----
          "kind":         "base",              # "base" | "skin"
          "skin_slug":    null,                # e.g. "marble_pantheon"
          "skin_name":    null,                # e.g. "Marble Pantheon"
          "skin_axis":    null,                # "cultural" | "anatomical"
          "rarity":       null                 # "rare" | "super_rare" (for shop)
        }
      ]
    }

Status semantics:
  - "active":    file exists, eligible for promotion
  - "pending":   manifest entry reserved, file not yet written (gen in flight)
  - "discarded": file exists but hidden from default views (recoverable)

Concurrency: a per-card threading.Lock protects manifest read-modify-write. The
process-level lock is sufficient because the FastAPI worker runs single-process
and the generation script runs one card at a time. If we ever fork generation,
move to a file lock (fcntl.flock) on `manifest.json`.
"""
from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---- canonical paths --------------------------------------------------------

CARDS_REPO_ART = Path(
    "/opt/agents/projects/daimon-cards/art/v1_alpha"
)
PREVIEW_DIR = Path("/opt/leeroy-web/uploads/cards")

_DIRS_INITIALIZED = False


def _ensure_dirs() -> None:
    """Create top-level directories on first use, not at import time."""
    global _DIRS_INITIALIZED
    if _DIRS_INITIALIZED:
        return
    CARDS_REPO_ART.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    _DIRS_INITIALIZED = True

# ---- per-card locks ---------------------------------------------------------

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(card_id: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lk = _LOCKS.get(card_id)
        if lk is None:
            lk = threading.Lock()
            _LOCKS[card_id] = lk
        return lk


# ---- paths ------------------------------------------------------------------

def card_dir(card_id: str) -> Path:
    return CARDS_REPO_ART / card_id


def variants_dir(card_id: str) -> Path:
    return card_dir(card_id) / "variants"


def manifest_path(card_id: str) -> Path:
    return card_dir(card_id) / "manifest.json"


def variant_path(card_id: str, vid: str) -> Path:
    return variants_dir(card_id) / f"{vid}.png"


def base_png_path(card_id: str) -> Path:
    return card_dir(card_id) / "base.png"


def preview_path(card_id: str, name: str) -> Path:
    """name e.g. 'base.png' or 'v3.png'."""
    return PREVIEW_DIR / card_id / name


# ---- manifest read/write ----------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_manifest(card_id: str) -> dict[str, Any]:
    return {"card_id": card_id, "canonical": None, "variants": []}


def load_manifest(card_id: str) -> dict[str, Any]:
    """Load (or synthesise) the manifest for a card. Never mutates disk."""
    _ensure_dirs()
    p = manifest_path(card_id)
    if not p.exists():
        return _empty_manifest(card_id)
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        # Corrupt manifest → return empty so callers can rebuild rather than crash.
        return _empty_manifest(card_id)


def save_manifest(card_id: str, manifest: dict[str, Any]) -> None:
    """Atomically replace manifest.json. Caller must hold _lock_for(card_id)."""
    _ensure_dirs()
    p = manifest_path(card_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=False))
    tmp.replace(p)


# ---- variant id allocation --------------------------------------------------

def _next_variant_id(manifest: dict[str, Any]) -> str:
    """Return the next sequential variant id (v0, v1, …) — never reuses."""
    used = {v["id"] for v in manifest.get("variants", [])}
    n = 0
    while f"v{n}" in used:
        n += 1
    return f"v{n}"


# ---- core mutations (each grabs the per-card lock) --------------------------

def reserve_variant(
    card_id: str,
    *,
    seed: int,
    seed_offset: int,
    model: str,
    prompt_version: str,
    kind: str = "base",
    skin_slug: Optional[str] = None,
    skin_name: Optional[str] = None,
    skin_axis: Optional[str] = None,
    rarity: Optional[str] = None,
) -> str:
    """Reserve the next variant id and append a status='pending' entry.

    Returns the new variant id. Caller must subsequently call
    `commit_variant(card_id, vid, png_bytes, ...)` once generation succeeds,
    or `cancel_variant(card_id, vid)` on failure.

    Skin metadata (kind/skin_slug/skin_name/skin_axis/rarity) is optional —
    when omitted, the variant is recorded as a "base" variant (legacy schema
    compatible). When provided, downstream consumers (shop, equip UI) can
    filter and address the variant by its skin slug.
    """
    if kind not in {"base", "skin"}:
        raise ValueError(f"invalid kind: {kind!r} (expected 'base' or 'skin')")
    if kind == "skin" and not skin_slug:
        raise ValueError("kind='skin' requires skin_slug")
    if skin_axis is not None and skin_axis not in {"cultural", "anatomical"}:
        raise ValueError(f"invalid skin_axis: {skin_axis!r}")
    if rarity is not None and rarity not in {"rare", "super_rare"}:
        raise ValueError(f"invalid rarity: {rarity!r}")
    with _lock_for(card_id):
        m = load_manifest(card_id)
        vid = _next_variant_id(m)
        entry = {
            "id": vid,
            "seed": seed,
            "seed_offset": seed_offset,
            "created_at": _now_iso(),
            "status": "pending",
            "model": model,
            "prompt_version": prompt_version,
            "kind": kind,
            "skin_slug": skin_slug,
            "skin_name": skin_name,
            "skin_axis": skin_axis,
            "rarity": rarity,
        }
        m["variants"].append(entry)
        save_manifest(card_id, m)
        return vid


def find_skin_variant(card_id: str, skin_slug: str) -> Optional[dict[str, Any]]:
    """Look up an existing variant by its skin_slug. Returns the variant entry
    (without acquiring the lock) or None if no such skin has been generated.

    Used by production runners for idempotent re-runs — if a skin already
    exists for a card, skip the generation rather than producing a duplicate.
    """
    for v in load_manifest(card_id).get("variants", []):
        if v.get("skin_slug") == skin_slug and v.get("status") in {"active", "pending"}:
            return v
    return None


def commit_variant(card_id: str, vid: str, png_bytes: bytes,
                   *, promote: bool = False) -> None:
    """Write the generated PNG to disk and flip status to 'active'.

    If `promote` is True or the card has no current canonical, this variant
    becomes canonical (base.png + preview/base.png are mirrored to it).
    """
    with _lock_for(card_id):
        vp = variant_path(card_id, vid)
        vp.parent.mkdir(parents=True, exist_ok=True)
        vp.write_bytes(png_bytes)

        # Always publish the per-variant preview so the FE can render it.
        prev = preview_path(card_id, f"{vid}.png")
        prev.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(vp, prev)

        m = load_manifest(card_id)
        for v in m["variants"]:
            if v["id"] == vid:
                v["status"] = "active"
                break
        else:
            # The reservation was lost (manifest replaced under us). Rebuild.
            m["variants"].append({
                "id": vid,
                "seed": 0, "seed_offset": 0,
                "created_at": _now_iso(),
                "status": "active",
                "model": "unknown", "prompt_version": "unknown",
            })

        if promote or m.get("canonical") is None:
            m["canonical"] = vid
            _publish_canonical_locked(card_id, vid)

        save_manifest(card_id, m)


def cancel_variant(card_id: str, vid: str) -> None:
    """Drop a pending reservation (e.g. generation errored)."""
    with _lock_for(card_id):
        m = load_manifest(card_id)
        m["variants"] = [v for v in m["variants"] if v["id"] != vid]
        save_manifest(card_id, m)


def set_canonical(card_id: str, vid: str) -> dict[str, Any]:
    """Promote `vid` to canonical and mirror its bytes to base.png + preview."""
    with _lock_for(card_id):
        m = load_manifest(card_id)
        match = next((v for v in m["variants"] if v["id"] == vid), None)
        if match is None:
            raise ValueError(f"unknown variant {vid} for {card_id}")
        if match["status"] != "active":
            raise ValueError(f"variant {vid} is {match['status']}, only 'active' variants can be canonical")
        m["canonical"] = vid
        _publish_canonical_locked(card_id, vid)
        save_manifest(card_id, m)
        return m


def set_status(card_id: str, vid: str, status: str) -> dict[str, Any]:
    """Mark a variant active/discarded. Discarding the canonical clears canonical."""
    if status not in {"active", "discarded"}:
        raise ValueError(f"invalid status: {status}")
    with _lock_for(card_id):
        m = load_manifest(card_id)
        match = next((v for v in m["variants"] if v["id"] == vid), None)
        if match is None:
            raise ValueError(f"unknown variant {vid} for {card_id}")
        match["status"] = status
        if status == "discarded" and m.get("canonical") == vid:
            # Canonical was discarded → fall back to most recent active variant
            actives = [v for v in m["variants"] if v["status"] == "active"]
            if actives:
                fallback = actives[-1]["id"]
                m["canonical"] = fallback
                _publish_canonical_locked(card_id, fallback)
            else:
                m["canonical"] = None
                # Leave base.png alone — operator can choose what happens next.
        save_manifest(card_id, m)
        return m


# ---- internal: publish canonical bytes -------------------------------------

def _publish_canonical_locked(card_id: str, vid: str) -> None:
    """Copy variant PNG to base.png + preview/base.png. Lock must be held."""
    src = variant_path(card_id, vid)
    if not src.exists():
        # File missing — nothing we can do here. Caller should have committed.
        return
    base = base_png_path(card_id)
    base.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, base)
    pbase = preview_path(card_id, "base.png")
    pbase.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, pbase)


# ---- helpers for callers ----------------------------------------------------

def used_seed_offsets(card_id: str) -> set[int]:
    """All seed offsets ever used (active, pending, or discarded). Used by the
    re-roll endpoint to pick a fresh offset."""
    return {v.get("seed_offset", 0) for v in load_manifest(card_id).get("variants", [])}


def list_active_variants(card_id: str) -> list[dict[str, Any]]:
    return [v for v in load_manifest(card_id).get("variants", []) if v["status"] == "active"]
