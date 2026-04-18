# ArcGIS Bulk Publishing Automation

This repository contains a Python automation script for bulk publishing ArcGIS content to ArcGIS Enterprise using the ArcGIS Python API.

It supports publishing multiple content types from a local input folder and automatically creates related web items based on the source package type.

## Supported Content Types

The script currently supports:

- `.zip` / `.sd` → Hosted Feature Services
- `.vtpk` → Vector Tile Services
- `.slpk` → Scene Services

In addition to publishing services, the script can also create:

- **Web Maps** for hosted feature services
- **Web Scenes** for scene services

## Use Cases

This script is useful for:

- bulk content publishing during test setup
- portal content creation for performance or scale validation
- automating repetitive publishing workflows
- quickly generating hosted services, web maps, and web scenes
- preparing ArcGIS Enterprise environments with sample content

## Key Features

- bulk publishes supported ArcGIS content types from a folder
- creates required target folders automatically
- skips already existing services based on title lookup
- creates web maps for feature services
- creates web scenes for scene services
- tracks publish counts by service type
- cleans up partially created items on failure
- prints a summary at the end of execution

## How to Run

**Install dependency:**
```bash
pip install arcgis
```

**Set credentials via environment variables (recommended for CI):**
```bash
export ARCGIS_URL=https://mygis.example.com/portal
export ARCGIS_USER=admin
export ARCGIS_PASSWORD=secret
```

**Run the script:**
```bash
python publishing_directory.py
```

Place your source files (`.zip`, `.sd`, `.vtpk`, `.slpk`) in the `uploads/` folder before running. The script will iterate through them, publish each to your target ArcGIS Enterprise portal, create associated web maps or web scenes where applicable, and print a summary of what was published.

**Sample uploads included:**
- `uploads/Building_scenelayer.slpk` — scene layer package (publishes as a Scene Service + Web Scene)
- `uploads/NZ_Jan.vtpk` — vector tile package (publishes as a Vector Tile Service)
- `uploads/SG_NationalScenicAreas_1998.zip` — shapefile (publishes as a Hosted Feature Service + Web Map)

## Repository Structure

```text
publishing/
├── README.md
├── publishing_directory.py
└── uploads/
    ├── Building_scenelayer.slpk
    ├── NZ_Jan.vtpk
    └── SG_NationalScenicAreas_1998.zip
