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

## Repository Structure

```text
arcgis-bulk-publishing/
│── README.md
│── bulk_publish.py
│── Uploads/
│── logs/
│── docs/
