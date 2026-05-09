# daimon-cards

Card definitions + art metadata for [DAIMON](https://github.com/aurorasuperbot/daimon).

## What lives here

- `schema/card.schema.json` — JSON schema for a card.
- `packs/<pack-name>/*.json` — pre-built loadout definitions (starter / legendary).
- `art/<pack>/.version` + `.checksum` + `<card_id>/manifest.json` — variant metadata for the art-pack ([format](art/README.md)).
- `CHANGELOG.md` — every card change, every release.

## What does NOT live here

- **Card art binaries (PNGs).** They ship via [GitHub Releases](https://github.com/aurorasuperbot/daimon-cards/releases) (`art-vX.Y` tags). The engine auto-fetches the matching pack on first run.
- The engine. Cards are pure data. The engine consumes them.
- Match state, trade history, leaderboards. That's `daimon-arena`.

## How art is delivered

```
pip install daimon
daimon match
  daimon: fetching art-v1.0 (908 MB) ... [████████████] 100%
  [match starts]
```

Subsequent invocations check for newer `art-v*` releases (rate-limited, 24h) and atomically swap in the background. See [`art/README.md`](art/README.md) for fetch details, pinning, and opt-out.

## Editing rules

- All changes via pull request.
- CODEOWNERS gates the entire repo.
- A card change requires a CHANGELOG entry in the same PR.
- Stat changes require an explanation: what build was unbalanced, what data justifies the change.
- Re-rolled art requires a new `art-vX.Y` release (build via `scripts/build_art_manifest.py`).

## Why a separate repo from the engine

The engine is mechanical — it changes when game rules change. The cards repo changes when *content* changes. Separating them means:
- Adding a card doesn't bump the engine version.
- Re-balancing a card doesn't require a new engine release.
- Re-rolled art is a new GH Release, not an engine ship.
- Different review surface: engine PRs need code review, card PRs need design review.

## Repo layout

```
daimon-cards/
├── schema/card.schema.json    # card JSON schema
├── packs/                     # pre-built loadouts
│   ├── starter/*.json
│   └── legendary/*.json
├── art/
│   ├── README.md              # art-pack delivery docs
│   └── v1_alpha/
│       ├── .version           # "art-v1.0"
│       ├── .checksum          # sha256 of v1_alpha.tar.gz
│       └── <card_id>/
│           └── manifest.json  # variant metadata
├── CHANGELOG.md
├── CODEOWNERS
├── LICENSE                    # PolyForm Noncommercial 1.0.0
└── README.md
```

Total repo size: ~1 MB. Art tarball (released separately): ~908 MB.
