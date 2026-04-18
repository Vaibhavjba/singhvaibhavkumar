# ArcGIS REST Services Cookbook

## Overview
A practical reference repository for working with ArcGIS REST Services.

## What this repository covers
- Service discovery and metadata
- Query operations
- Attribute and spatial filtering
- Feature service access patterns
- Geocoding and reverse geocoding
- Authentication basics

## Tools and Technologies
- ArcGIS Enterprise
- ArcGIS REST API
- Postman
- JavaScript / Python examples where applicable

## Repository Structure
- `service-discovery/` - finding and understanding services
- `query-examples/` - layer and feature querying patterns
- `filter-examples/` - filtering examples for practical use cases
- `feature-service-examples/` - common feature layer operations
- `geocoding-examples/` - location search examples
- `authentication-notes/` - authentication and token concepts

## Why this repository
This repository demonstrates how ArcGIS services are consumed in enterprise GIS and web GIS solutions.

## Roadmap
- Add more request/response examples
- Add JavaScript and Python consumption samples
- Add publishing and service best-practice notes

---

## Scripts

### `sanity_report_generator.py`

**Problem it solves:** After an ArcGIS Enterprise upgrade, teams run hundreds of validation tests across categories (Admin API, Raster, Notebook, Security, Publishing, etc.) and need a shareable, visual summary of what passed, what failed, and what regressed compared to pre-upgrade results. Emailing a raw JSON file is impractical. This script turns a structured `sanity_results.json` into a self-contained HTML dashboard that anyone can open in a browser — no server required.

**What it produces:**
- Summary stats: total executed / passed / failed / post-only tests
- Pass rate progress bar (green gradient when clean, red split on failures)
- Pre vs. post delta table with regression (`PASS → FAIL`) and fix (`FAIL → PASS`) highlights
- Interactive Plotly bar chart of results by category (Admin API, Raster, Services, etc.)
- Failures detail section for quick triage

**Input JSON schema:**
```json
{
  "pre_upgrade":  { "CATEGORY: Test Name": {"status": "PASS", "message": "..."} },
  "post_upgrade": { "CATEGORY: Test Name": {"status": "FAIL", "message": "..."} }
}
```

**Install:**
```bash
pip install plotly
```

**Run:**
```bash
# Quick demo using the included sample
python sanity_report_generator.py --input sanity_results_sample.json

# Named report for a specific build
python sanity_report_generator.py \
  --input sanity_results.json \
  --output report_build8230.html \
  --title "Build 8230"
```

Output is a single `report.html` file (or whatever `--output` specifies) with no external dependencies — open it in any browser or attach it to a release ticket.