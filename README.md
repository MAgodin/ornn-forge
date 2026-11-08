# Ornn's Forge — Live Champion Build Picker

Free, static website hosted on GitHub Pages. Select any supported League of Legends champion, switch role when available, and see purchasable items from recent OP.GG ranked builds, with Riot's official icons.

Live site: https://magodin.github.io/ornn-forge/

## Automatic build updates
The GitHub Actions workflow `.github/workflows/refresh-builds.yml` is scheduled every day at **04:17 UTC**, and can also be started manually with **Actions → Refresh LoL champion builds → Run workflow**.

The script `scripts/refresh_builds.py` attempts to collect per-champion and per-role popular builds from OP.GG's MCP endpoint, filters out boots and non-legendary items, and writes `builds.json` with the patch and timestamp. It retains previous data for individual failed fetches and refuses to overwrite everything when overall coverage is too low.

**IMPORTANT: The updater is experimental, and its first GitHub Actions run failed before publishing any `builds.json`. Verify the latest workflow run is green and `builds.json` exists before claiming builds refresh automatically.** If Actions is blocked, open the failed workflow run and inspect the error; make sure Actions and workflow write permissions are enabled in repository settings.

The site displays warnings for unavailable or outdated live data instead of calling static fallback builds current. **Items shown are popular build items, not proven optimal Ornn upgrades.** An item must be owned and upgradable; the game follows inventory order.

## Data attribution
- Build data: OP.GG (community public MCP endpoint, availability subject to change)
- Champion and item artwork: Riot Games Data Dragon
- Fan-made tool, not endorsed by Riot Games

## Free hosting
Settings → Pages → Deploy from branch → main → / (root). No paid subscription is needed.
