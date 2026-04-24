# Card Art

Card-art binaries (PNGs) **do not live in this repo**. They ship via [GitHub Releases](https://github.com/aurorasuperbot/daimon-cards/releases) as versioned tarballs (`art-vX.Y` tags).

## What lives here

- `<pack>/.version` — currently-pinned art-pack version (e.g. `art-v1.0`)
- `<pack>/.checksum` — sha256 of the tarball asset, used to verify download
- `<pack>/<card_id>/manifest.json` — variant metadata (seed, prompt-version, status, canonical pick)

## How the engine fetches art

The `daimon` engine auto-fetches the matching art-pack on first run and on subsequent updates:

```
$ daimon match
daimon: fetching art-v1.0 (908 MB) ... [████████████] 100%
daimon: extracted to ~/.daimon/art/v1_alpha/
[match starts]
```

After the initial fetch, every `daimon` invocation does a rate-limited (24h) check for newer `art-v*` releases. If newer, the engine downloads and atomically swaps in the background — the next invocation sees the update.

See [`daimon/update.py`](https://github.com/aurorasuperbot/daimon/blob/main/daimon/update.py) for the implementation.

## Manual fetch

If you'd rather fetch the art-pack yourself (e.g. CI cache, offline install):

```bash
# Latest
gh release download --repo aurorasuperbot/daimon-cards --pattern 'v1_alpha.tar.gz' \
  --dir ~/.daimon/art-staging/

# Specific version
gh release download art-v1.0 --repo aurorasuperbot/daimon-cards \
  --pattern 'v1_alpha.tar.gz' --dir ~/.daimon/art-staging/

# Verify + extract
cd ~/.daimon/art-staging
sha256sum -c <(echo "$(cat ~/.daimon/art/v1_alpha/.checksum)")
tar xzf v1_alpha.tar.gz -C ~/.daimon/
```

## Layout after extraction

```
~/.daimon/art/v1_alpha/<card_id>/
  base.png          # canonical mirror, served by FE/render layer
  manifest.json     # variant metadata
  variants/
    v0.png          # initial generation
    v1.png          # re-rolls if any
    ...
```

## Pinning a version

To pin to a specific art-pack version (reproducible installs, CI):

```bash
export DAIMON_PIN_ART=art-v1.0
daimon match
```

Or in `~/.config/daimon/config.toml`:

```toml
[art]
pin_version = "art-v1.0"
```

## Opting out of auto-update

```bash
export DAIMON_NO_AUTO_UPDATE=1
```

## Manifest format

Each `<card_id>/manifest.json` records the per-card variant history:

```json
{
  "card_id": "abyss_warden",
  "canonical": "v0",
  "variants": [
    {
      "id": "v0",
      "seed": 12345,
      "seed_offset": 0,
      "created_at": "2026-04-24T05:15:31Z",
      "status": "active",
      "model": "nai-diffusion-4-5-full",
      "prompt_version": "miura_v1"
    }
  ]
}
```

`status` is one of `active`, `pending`, `discarded`. `canonical` is the variant ID currently mirrored to `base.png`.
