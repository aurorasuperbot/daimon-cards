# Changelog

All notable changes to DAIMON card definitions.

## [Unreleased]

## [art-v1.0] — 2026-04-25

### Added
- First public art pack release. 200 cards × canonical (v0) variants + skin
  variants (v1, v2 where applicable, from the 2026-04-24 NovelAI art pass).
- `art/v1_alpha/.version` set to `art-v1.0`.
- `art/v1_alpha/.checksum` records the sha256 of the released `v1_alpha.tar.gz`.
- `art/variants_lib.py` — manifest read/write authority module (used by the
  art-pass script and the FE Cards-tab routes).
- 200 manifests now carry `variants[]` entries with `kind: "skin"` for the
  cards that received cultural / anatomical skin re-rolls.

### Notes
- Tarball: `v1_alpha.tar.gz` (~1.6 GB) attached to the GH Release.
- Engine compat: requires `daimon-engine` with `COMPAT_ART_MAJOR == 1`.
- Auto-fetched by `daimon match` / `daimon shop` on first run; pin via
  `DAIMON_PIN_ART=art-v1.0` to lock.

## [Initial layout]

### Added
- `schema/card.schema.json` — V1 card schema (engine-coupled).
- `packs/starter/` — 6 starter common cards, one per slot:
  - `starter_scout_head`
  - `starter_iron_torso`
  - `starter_blade_arm` (ARM_L)
  - `starter_buckler_arm` (ARM_R)
  - `starter_runner_legs`
  - `starter_steady_core`
- `packs/legendary/plasma_lance.json` — V1 reference legendary card.
- Initial `art/` directory layout (Git LFS).

## Versioning

Card packs use semver tags published as OCI artifacts:
`ghcr.io/aurorasuperbot/daimon-cardpacks:starter-v1.0.0`

- MAJOR: stat changes that invalidate prior loadouts (rare, requires deprecation cycle).
- MINOR: new cards added.
- PATCH: art-only updates, flavor-text fixes, no engine impact.
