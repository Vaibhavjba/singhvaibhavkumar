# ArcGIS Python API

Python automation scripts for ArcGIS Enterprise and ArcGIS Online — administration, health validation, and content publishing workflows.

---

## Scripts

### `src/portal_health_check.py`

**Problem it solves:** After an ArcGIS Enterprise upgrade or configuration change, operators need a fast, scriptable way to confirm the portal is reachable, authentication works, and critical system services (PublishingTools, CachingTools, SyncTools) are in a `STARTED` state — without manually clicking through the admin UI. This script provides that check in one command and integrates into CI/CD pipelines via structured exit codes.

**What it checks:**
- Portal URL reachability and token generation
- Portal version and Enterprise vs. ArcGIS Online detection
- System service states: `Hosted/PublishingTools`, `System/CachingTools`, `System/SyncTools`, `System/PublishingTools`

**Exit codes:** `0` all checks passed · `1` one or more checks failed · `2` connection / auth error

**Install:**
```bash
pip install arcgis
```

**Run:**
```bash
# Table output (human-readable)
python src/portal_health_check.py \
  --url https://mygis.example.com/portal \
  --user admin \
  --password secret

# JSON output (for CI pipelines / downstream parsing)
python src/portal_health_check.py --output json

# Recommended: credentials via environment variables
export ARCGIS_URL=https://mygis.example.com/portal
export ARCGIS_USER=admin
export ARCGIS_PASSWORD=secret
python src/portal_health_check.py --output json
```

---

### `src/publishing/` — Bulk Publishing Automation

See [`src/publishing/README.md`](src/publishing/README.md) for the bulk publishing script that handles `.zip`/`.sd` → Hosted Feature Services, `.vtpk` → Vector Tile Services, and `.slpk` → Scene Services.