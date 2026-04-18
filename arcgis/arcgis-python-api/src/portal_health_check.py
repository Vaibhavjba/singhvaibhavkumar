#!/usr/bin/env python3
"""
portal_health_check.py

Validates ArcGIS portal connectivity, token generation, and system service states.
Works against both ArcGIS Enterprise and ArcGIS Online.

Usage:
    python portal_health_check.py --url https://mygis.example.com/portal --user admin --password secret
    python portal_health_check.py --url https://www.arcgis.com --user me@org.com --password secret --output json

    # Credentials via environment variables (recommended for CI):
    export ARCGIS_URL=https://mygis.example.com/portal
    export ARCGIS_USER=admin
    export ARCGIS_PASSWORD=secret
    python portal_health_check.py --output json

Exit codes:
    0  All checks passed
    1  One or more checks failed
    2  Connection / auth error

Requirements:
    pip install arcgis
"""

import argparse
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# System services expected to be STARTED in a healthy Enterprise deployment
SYSTEM_SERVICES = [
    "Hosted/PublishingTools",
    "System/CachingTools",
    "System/SyncTools",
    "System/PublishingTools",
]


def check_system_service(gis, service_name: str) -> dict:
    """Check a single system service state via the admin API."""
    try:
        svc = gis.admin.services.get(service_name)
        state = svc.status.get("realTimeState", "UNKNOWN")
        configured = svc.status.get("configuredState", "UNKNOWN")
        ok = state == "STARTED"
        return {
            "service": service_name,
            "realTimeState": state,
            "configuredState": configured,
            "ok": ok,
        }
    except Exception as exc:
        return {
            "service": service_name,
            "realTimeState": "ERROR",
            "configuredState": "ERROR",
            "ok": False,
            "error": str(exc),
        }


def check_portal(url: str, username: str, password: str) -> dict:
    """Run all health checks and return a structured result dict."""
    from arcgis.gis import GIS

    result = {
        "portal_url":  url,
        "token_ok":    False,
        "version":     None,
        "is_enterprise": None,
        "services":    [],
        "errors":      [],
    }

    # ── Token / connection ────────────────────────────────────────────────
    try:
        gis = GIS(url, username, password, verify_cert=False)
        result["token_ok"]     = True
        result["version"]      = gis.properties.get("currentVersion", "unknown")
        result["is_enterprise"] = not gis.properties.get("isPortal", True) or url != "https://www.arcgis.com"
        log.info(f"Connected to {url}  (version: {result['version']})")
    except Exception as exc:
        result["errors"].append(f"Connection failed: {exc}")
        log.error(f"Connection failed: {exc}")
        return result

    # ── System services (Enterprise only) ────────────────────────────────
    if result["is_enterprise"]:
        log.info("Checking system services...")
        for svc_name in SYSTEM_SERVICES:
            svc_result = check_system_service(gis, svc_name)
            result["services"].append(svc_result)
            symbol = "✅" if svc_result["ok"] else "❌"
            log.info(f"  {symbol} {svc_name}: {svc_result['realTimeState']}")
    else:
        log.info("ArcGIS Online detected — skipping system service checks.")

    return result


def print_table(result: dict) -> bool:
    ok = result["token_ok"] and all(s["ok"] for s in result["services"])
    print(f"\nPortal:   {result['portal_url']}")
    print(f"Version:  {result['version']}")
    print(f"Token:    {'✅ OK' if result['token_ok'] else '❌ FAILED'}")
    if result["services"]:
        print("\nSystem Services:")
        for s in result["services"]:
            symbol = "✅" if s["ok"] else "❌"
            print(f"  {symbol} {s['service']:40s} {s['realTimeState']}")
    if result["errors"]:
        print("\nErrors:")
        for e in result["errors"]:
            print(f"  ❌ {e}")
    print(f"\nOverall: {'✅ HEALTHY' if ok else '❌ DEGRADED'}\n")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="ArcGIS portal health check")
    parser.add_argument("--url",      default=os.environ.get("ARCGIS_URL"),
                        help="Portal URL (or set ARCGIS_URL)")
    parser.add_argument("--user",     default=os.environ.get("ARCGIS_USER"),
                        help="Username (or set ARCGIS_USER)")
    parser.add_argument("--password", default=os.environ.get("ARCGIS_PASSWORD"),
                        help="Password (or set ARCGIS_PASSWORD)")
    parser.add_argument("--output", choices=["table", "json"], default="table")
    args = parser.parse_args()

    if not args.url or not args.user or not args.password:
        parser.error("--url, --user, and --password are required (or set ARCGIS_URL / ARCGIS_USER / ARCGIS_PASSWORD).")

    result = check_portal(args.url, args.user, args.password)

    if args.output == "json":
        print(json.dumps(result, indent=2))
        all_ok = result["token_ok"] and all(s["ok"] for s in result["services"])
    else:
        all_ok = print_table(result)

    if not result["token_ok"]:
        sys.exit(2)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
