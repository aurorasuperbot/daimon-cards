# Card Art

Card-art binaries (PNGs) **do not live in this repo**. They ship via [GitHub Releases](https://github.com/aurorasuperbot/daimon-cards/releases) as versioned tarballs (`art-vX.Y` tags).

## What lives here

- `<pack>/.version` — currently-pinned art-pack version (e.g. `art-v1.0`)
- `<pack>/.checksum` — sha256 of the tarball asset, used to verify download
- `<pack>/<card_id>/manifest.json` — variant metadata (seed, prompt-version, status, canonical pick)

## How the engine fetches art

The `daimon` engine uses a lazy per-card fetch model. On first run it downloads the small manifest (~50KB) and then fetches individual card tarballs on demand as each card first needs to render:

```
$ daimon match
daimon: fetching manifest for art-v1.1 ... done (50 KB)
daimon: fetching starter cards (6 of 200) ... [████████████] 100%
[match starts]
```

After the initial manifest fetch, every `daimon` invocation does a rate-limited (24h) check for newer `art-v*` releases. If a newer manifest is found, updated per-card tarballs are downloaded in the background — only cards whose sha256 changed are re-fetched.

See [`daimon/update.py`](https://github.com/aurorasuperbot/daimon/blob/main/daimon/update.py) for the implementation.

## Manual fetch

If you'd rather fetch art yourself (e.g. CI cache, offline install):

```bash
# Download manifest + all per-card tarballs for a specific version
gh release download art-v1.1 --repo aurorasuperbot/daimon-cards \
  --dir ~/.daimon/art-staging/

# Verify manifest
cd ~/.daimon/art-staging
sha256sum -c manifest.json.sha256

# Verify + extract individual cards
sha256sum -c card_abyss_warden.tar.gz.sha256
tar xzf card_abyss_warden.tar.gz -C ~/.daimon/art/v1_alpha/abyss_warden/
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
