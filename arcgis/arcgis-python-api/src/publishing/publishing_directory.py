#!/usr/bin/env python3
"""
Bulk publish ArcGIS content:
- .zip / .sd  -> hosted feature service + web map
- .vtpk       -> vector tile service
- .slpk       -> scene service + web scene
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime as dt
from pathlib import Path
from typing import Iterable

from arcgis.gis import GIS
from arcgis.map import Map
import sys
# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

PORTAL_NAME = "devems00543.esri.com"
CONTEXT = "enhncd"
USERNAME = os.getenv("ARCGIS_USERNAME", "administrator")
PASSWORD = os.getenv("ARCGIS_PASSWORD", "esri.agp1")
VERIFY_CERT = False

FOLDER_PATH = Path(sys.path[0], "Uploads")
MAX_WORKERS = min(8, (os.cpu_count() or 4))

FOLDERS = {
    "feature": "Hosted Feature Services",
    "tile": "Tile Services",
    "webmap": "WEB MAP",
    "scene": "Scene Services",
    "webscene": "Web Scene",
}

SUPPORTED_EXTENSIONS = {".sd", ".zip", ".vtpk", ".slpk"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

@dataclass
class PublishStats:
    feature_services: int = 0
    vector_tile_services: int = 0
    scene_services: int = 0
    web_maps: int = 0
    web_scenes: int = 0
    failed_services: list[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def connect_gis() -> GIS:
    """Create GIS connection."""
    url = f"https://{PORTAL_NAME}/{CONTEXT}"
    try:
        return GIS(url=url, username=USERNAME, password=PASSWORD, verify_cert=VERIFY_CERT)
    except Exception as exc:
        logging.error(f"Failed to connect to GIS portal: {exc}")
        raise


def ensure_folders(gis: GIS) -> None:
    """Create required folders if they do not already exist."""
    existing = {f.name for f in gis.content.folders.list()}
    for folder in FOLDERS.values():
        if folder not in existing:
            gis.content.create_folder(folder)
            logging.info("Created folder: %s", folder)


def find_files(folder: Path) -> list[Path]:
    """Return supported files from the input folder."""
    return [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]


def service_exists(gis: GIS, service_name: str) -> bool:
    """Check if content already exists by title."""
    return bool(gis.content.search(query=f'title:"{service_name}"', max_items=10))


def delete_matching_items(gis: GIS, name: str) -> None:
    """Delete partial items created during a failed publish."""
    items = gis.content.search(query=f'title:"{name}"', max_items=100)
    if items:
        logging.warning("Deleting partial items for: %s", name)
        gis.content.delete_items(items)


def web_scene_payload(item_id: str, title: str, url: str) -> str:
    """Return Web Scene JSON definition."""
    data = {
        "operationalLayers": [{
            "itemId": item_id,
            "title": title,
            "visibility": True,
            "opacity": 1,
            "url": url,
            "layerType": "ArcGISSceneServiceLayer",
        }],
        "baseMap": {
            "baseMapLayers": [{
                "id": "world-street-map",
                "visibility": True,
                "opacity": 1,
                "layerDefinition": {},
                "url": "https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer",
                "layerType": "ArcGISTiledMapServiceLayer",
            }],
            "title": "World Street Map",
            "elevationLayers": [{
                "url": "https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer",
                "id": "globalElevation_0",
                "layerType": "ArcGISTiledElevationServiceLayer",
            }],
        },
        "spatialReference": {"wkid": 102100, "latestWkid": 3857},
        "version": "1.4",
        "viewingMode": "global",
        "tables": [],
    }
    return json.dumps(data)


# -----------------------------------------------------------------------------
# Publish functions
# -----------------------------------------------------------------------------

def publish_vector_tile(gis: GIS, file_path: Path, stats: PublishStats) -> None:
    """Publish a vector tile package."""
    item = gis.content.add({}, data=str(file_path), folder=FOLDERS["tile"])
    layer = item.publish()
    layer.share(org=True)
    stats.vector_tile_services += 1
    logging.info("Published vector tile service: %s", file_path.stem)


def publish_feature_service(gis: GIS, file_path: Path, stats: PublishStats) -> None:
    """Publish hosted feature service and create its web map."""
    item = gis.content.add({}, data=str(file_path), folder=FOLDERS["feature"])
    published = item.publish()
    published.share(org=True)
    stats.feature_services += 1

    webmap = Map()
    search_result = gis.content.search("title:" + published.title, item_type="Feature Service")
    webmap.content.add(search_result)
    
    web_map_properties = {
            "title": f"Web Map - {published.title}",
            "snippet": f"Created using ArcGIS Python API for {published.title}",
            "tags": "ArcGIS Python API, WebMap",
            "type": "Web Map",
    }
    webmap_item = webmap.save(item_properties=web_map_properties)
    webmap_item.share(org=True)
    stats.web_maps += 1
    logging.info("Published feature service and web map: %s", file_path.stem)


def publish_scene_service(gis: GIS, file_path: Path, stats: PublishStats) -> None:
    """Publish scene service and create its web scene."""
    item = gis.content.add({}, data=str(file_path), folder=FOLDERS["scene"])
    published = item.publish()
    published.share(org=True)
    stats.scene_services += 1

    webscene = gis.content.add(
        item_properties={
            "title": f"Web Scene - {published.title}",
            "type": "Web Scene",
            "snippet": f"Created using ArcGIS Python API for {published.title}",
            "tags": "ArcGIS Python API, Web Scene",
            "text": web_scene_payload(published.itemid, published.title, published.url),
        },
        folder=FOLDERS["webscene"],
    )
    webscene.share(org=True)
    stats.web_scenes += 1
    logging.info("Published scene service and web scene: %s", file_path.stem)


def publish_item(gis: GIS, file_path: Path) -> PublishStats:
    """Route file to the correct publisher."""
    stats = PublishStats()
    service_name = file_path.stem

    if service_exists(gis, service_name):
        logging.info("Skipping existing service: %s", service_name)
        return stats

    try:
        suffix = file_path.suffix.lower()
        if suffix == ".vtpk":
            publish_vector_tile(gis, file_path, stats)
        elif suffix == ".slpk":
            publish_scene_service(gis, file_path, stats)
        else:  # .zip / .sd
            publish_feature_service(gis, file_path, stats)
    except Exception as exc:
        stats.failed_services.append(service_name)
        logging.exception("Failed publishing %s: %s", file_path.name, exc)
        delete_matching_items(gis, service_name)

    return stats


def merge_stats(all_stats: Iterable[PublishStats]) -> PublishStats:
    """Merge per-task stats into one summary."""
    total = PublishStats()
    for s in all_stats:
        total.feature_services += s.feature_services
        total.vector_tile_services += s.vector_tile_services
        total.scene_services += s.scene_services
        total.web_maps += s.web_maps
        total.web_scenes += s.web_scenes
        total.failed_services.extend(s.failed_services)
    return total


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> None:
    start = dt.now()
    gis = connect_gis()

    ensure_folders(gis)

    if not FOLDER_PATH.exists():
        raise FileNotFoundError(f"Input folder not found: {FOLDER_PATH}")

    files = find_files(FOLDER_PATH)
    logging.info("Found %s files to process", len(files))

    results: list[PublishStats] = []

    # Reuse same GIS object to stay close to your original approach.
    # If you see thread-safety/session issues, create a new GIS connection per task.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(publish_item, gis, file): file for file in files}
        for future in as_completed(futures):
            file = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                logging.exception("Unhandled error for %s: %s", file.name, exc)

    summary = merge_stats(results)
    end = dt.now()

    print("\n--- Publish Summary ---")
    print(f"Start Time                  : {start:%d %B, %Y, %H:%M:%S %p}")
    print(f"End Time                    : {end:%d %B, %Y, %H:%M:%S %p}")
    print(f"Total Feature Services      : {summary.feature_services}")
    print(f"Total Scene Services        : {summary.scene_services}")
    print(f"Total Vector Tile Services  : {summary.vector_tile_services}")
    print(f"Total Web Maps              : {summary.web_maps}")
    print(f"Total Web Scenes            : {summary.web_scenes}")
    print(f"Failed Services             : {len(summary.failed_services)}")
    if summary.failed_services:
        print(f"Failed Service Names        : {', '.join(summary.failed_services)}")
    print(f"Elapsed Time                : {end - start}")


if __name__ == "__main__":
    main()