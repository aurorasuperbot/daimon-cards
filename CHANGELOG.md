# Changelog

All notable changes to DAIMON card definitions.

## [Unreleased]

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
