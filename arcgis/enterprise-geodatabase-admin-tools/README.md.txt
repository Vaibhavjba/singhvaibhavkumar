# Enterprise Geodatabase Admin Tools

## Overview
A practical repository for enterprise geodatabase administration, validation, and maintenance workflows.

## What this repository covers
- Connection and access checks
- Dataset and schema reviews
- Version management notes
- Publish-readiness validation
- Maintenance checklists

## Tools and Technologies
- ArcGIS Enterprise
- ArcGIS Pro
- Enterprise Geodatabase
- Python / SQL where applicable

## Repository Structure
- `connection-checks/` - database and access validation patterns
- `health-checks/` - dataset and publishing readiness checks
- `schema-tools/` - schema review and standardization notes
- `version-management/` - versioning support workflows
- `maintenance/` - operational maintenance guidance

## Why this repository
This repository highlights enterprise GIS administration knowledge that supports reliable publishing, data quality, and operational readiness.

## Roadmap
- Add geodatabase health scripts
- Add versioning examples
- Add common administration scenarios

---

## Scripts

### `health-checks/arcgis-service-endpoint-validator.py`

**Problem it solves:** During pre/post-upgrade validation, engineers need to confirm that a defined set of ArcGIS REST endpoints are reachable, returning valid responses, and not silently returning ArcGIS-level error bodies (HTTP 200 with `{"error": {...}}` in JSON). Running these checks manually in a browser or Postman for 20–50 endpoints is error-prone and slow. This script reads a YAML file of endpoint definitions, authenticates once, and validates all endpoints in sequence — designed as a CI/CD gate that exits non-zero on any failure.

**What it checks per endpoint:**
- HTTP 200 response (with retry on timeout)
- No `{"error": {...}}` block in the JSON response body
- All `expected_keys` are present in the response

**Exit codes:** `0` all endpoints healthy · `1` one or more failed · `2` config / auth error

**Install:**
```bash
pip install pyyaml requests
```

**Create an `endpoints.yml` file:**
```yaml
services:
  - name: REST Info
    url: https://mygis.example.com/portal/sharing/rest/info
    expected_keys: [currentVersion, owningSystemUrl]

  - name: Portal Self
    url: https://mygis.example.com/portal/sharing/rest/portals/self
    expected_keys: [id, name]

  - name: Admin Health Check
    url: https://mygis.example.com/gis/admin/healthCheck
    expected_keys: [success]
```

**Run:**
```bash
# With a pre-existing token (recommended for CI)
export ARCGIS_TOKEN=<your_token>
python health-checks/arcgis-service-endpoint-validator.py --endpoints endpoints.yml

# Auto-generate token from portal credentials
python health-checks/arcgis-service-endpoint-validator.py \
  --endpoints endpoints.yml \
  --portal https://mygis.example.com/portal \
  --user admin \
  --password secret

# JSON output for downstream pipeline consumption
python health-checks/arcgis-service-endpoint-validator.py \
  --endpoints endpoints.yml --output json
```