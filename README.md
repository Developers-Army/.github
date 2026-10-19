# Developers Army · `.github`

This repository holds the Developers Army organisation profile. GitHub shows
[`profile/README.md`](profile/README.md) on [github.com/Developers-Army](https://github.com/Developers-Army).

## Working on the profile

- Branch from `develop` (`feat/<slug>`), open a pull request into `develop`, then promote `develop` → `main`.
  The profile goes live when `main` changes.
- Copy follows the website's rules: facts only, public-facing, nothing internal.
  No people's names, no vendor or infrastructure names, and no unannounced products.
- Artwork lives in `profile/assets/`. Each image ships in a dark and a light version, and the README picks one to match the
  viewer's GitHub theme.

## Commands

No install or build. Python 3.10+ with `fontTools` and `brotli`, and Node 18+.

- `python scripts/build_art.py` regenerates every SVG in `profile/assets/` from the fonts in `scripts/fonts/` (offline).
  Edit the artwork there, not in the SVGs.
- `node scripts/check-content.mjs` fails if the profile mentions anything that must stay internal.
- `python scripts/check_svg.py` fails if an SVG is invalid, uses live text, scripts or outside resources, animates
  without a reduced-motion rule, or is missing its dark or light twin.
