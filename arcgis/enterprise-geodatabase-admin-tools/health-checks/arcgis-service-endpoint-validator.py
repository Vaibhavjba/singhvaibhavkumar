#!/usr/bin/env python3
"""
arcgis-service-endpoint-validator.py

Validates ArcGIS REST service endpoints defined in a YAML file. For each endpoint
it performs a token-authenticated GET and checks:
  - HTTP 200 response
  - No {"error": {...}} block in the JSON response
  - All expected_keys are present in the response

Designed for pre/post-upgrade sanity checks and CI/CD gates.

Usage:
    python arcgis-service-endpoint-validator.py --endpoints endpoints.yml --token <token>

    # Token from environment (recommended):
    export ARCGIS_TOKEN=<token>
    python arcgis-service-endpoint-validator.py --endpoints endpoints.yml

    # Run against a specific portal and generate fresh token:
    python arcgis-service-endpoint-validator.py \
        --endpoints endpoints.yml \
        --portal https://mygis.example.com/portal \
        --user admin --password secret

Exit codes:
    0  All endpoints healthy
    1  One or more endpoints failed
    2  Config / auth error

Sample endpoints.yml:
    services:
      - name: REST Info
        url: https://mygis.example.com/portal/sharing/rest/info
        expected_keys: [currentVersion, owningSystemUrl]
      - name: Portal Self
        url: https://mygis.example.com/portal/sharing/rest/portals/self
        expected_keys: [id, name]
      - name: Admin Health
        url: https://mygis.example.com/gis/admin/healthCheck
        expected_keys: [success]

Requirements:
    pip install pyyaml requests
"""

import argparse
import json
import os
import sys
import time
from typing import Optional

import requests
import urllib3
import yaml

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_TIMEOUT = (5, 30)   # (connect, read) seconds
MAX_RETRIES     = 2
RETRY_DELAY     = 3         # seconds between retries


# ── Token helper ─────────────────────────────────────────────────────────────
def get_token(portal_url: str, username: str, password: str,
              expiration: int = 60) -> Optional[str]:
    """Generate a short-lived ArcGIS token."""
    url = f"{portal_url.rstrip('/')}/sharing/rest/generateToken"
    payload = {
        "username":   username,
        "password":   password,
        "referer":    portal_url,
        "expiration": expiration,
        "f":          "json",
    }
    try:
        resp = requests.post(url, data=payload, verify=False, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            print(f"ERROR  Token generation failed: {data['error'].get('message', data['error'])}")
            return None
        return data.get("token")
    except Exception as exc:
        print(f"ERROR  Could not generate token: {exc}")
        return None


# ── Per-endpoint validation ──────────────────────────────────────────────────
def validate_endpoint(entry: dict, token: str) -> dict:
    url           = entry["url"]
    name          = entry.get("name", url)
    expected_keys = entry.get("expected_keys", [])
    method        = entry.get("method", "GET").upper()

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            params = {"f": "json"}
            if token:
                params["token"] = token

            if method == "POST":
                resp = requests.post(url, data=params, verify=False, timeout=DEFAULT_TIMEOUT)
            else:
                resp = requests.get(url, params=params, verify=False, timeout=DEFAULT_TIMEOUT)

            resp.raise_for_status()
            data = resp.json()

            # ArcGIS-level error (HTTP 200 but error in body)
            if "error" in data:
                code = data["error"].get("code", "?")
                msg  = data["error"].get("message", "")
                return {
                    "name": name, "url": url, "ok": False,
                    "reason": f"API error {code}: {msg}",
                    "attempts": attempt,
                }

            # Expected keys check
            missing = [k for k in expected_keys if k not in data]
            if missing:
                return {
                    "name": name, "url": url, "ok": False,
                    "reason": f"Missing response keys: {missing}",
                    "attempts": attempt,
                }

            return {"name": name, "url": url, "ok": True, "reason": "OK", "attempts": attempt}

        except requests.exceptions.Timeout:
            if attempt <= MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            return {"name": name, "url": url, "ok": False,
                    "reason": "Timed out after retries", "attempts": attempt}
        except requests.exceptions.ConnectionError as exc:
            return {"name": name, "url": url, "ok": False,
                    "reason": f"Connection error: {exc}", "attempts": attempt}
        except Exception as exc:
            return {"name": name, "url": url, "ok": False,
                    "reason": str(exc), "attempts": attempt}

    return {"name": name, "url": url, "ok": False, "reason": "Max retries exceeded", "attempts": MAX_RETRIES + 1}


# ── Entry point ──────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate ArcGIS REST service endpoints from a YAML definition file"
    )
    parser.add_argument("--endpoints", required=True,
                        help="Path to YAML file with endpoint definitions")
    parser.add_argument("--token",    default=os.environ.get("ARCGIS_TOKEN", ""),
                        help="ArcGIS token (or set ARCGIS_TOKEN env var)")
    parser.add_argument("--portal",   default=None,
                        help="Portal URL to generate a fresh token (requires --user / --password)")
    parser.add_argument("--user",     default=os.environ.get("ARCGIS_USER", ""),
                        help="Username for token generation")
    parser.add_argument("--password", default=os.environ.get("ARCGIS_PASSWORD", ""),
                        help="Password for token generation")
    parser.add_argument("--output", choices=["table", "json"], default="table")
    args = parser.parse_args()

    # ── Resolve token ────────────────────────────────────────────────────
    token = args.token
    if not token and args.portal:
        if not args.user or not args.password:
            parser.error("--user and --password required when generating token via --portal")
        token = get_token(args.portal, args.user, args.password)
        if not token:
            sys.exit(2)

    # ── Load endpoint definitions ─────────────────────────────────────────
    try:
        with open(args.endpoints, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR  Endpoints file not found: {args.endpoints}")
        sys.exit(2)
    except yaml.YAMLError as exc:
        print(f"ERROR  Invalid YAML: {exc}")
        sys.exit(2)

    endpoints = config.get("services", [])
    if not endpoints:
        print("WARNING  No endpoints defined in 'services:' key.")
        sys.exit(0)

    # ── Validate ──────────────────────────────────────────────────────────
    results = []
    for entry in endpoints:
        r = validate_endpoint(entry, token)
        results.append(r)
        if args.output == "table":
            symbol = "✅" if r["ok"] else "❌"
            retries = f" (attempt {r['attempts']})" if r["attempts"] > 1 else ""
            print(f"  {symbol} {r['name']:40s} {r['reason']}{retries}")

    if args.output == "json":
        print(json.dumps(results, indent=2))

    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed

    if args.output == "table":
        print(f"\n{passed}/{len(results)} endpoints healthy", end="")
        if failed:
            print(f"  ({failed} failed)")
        else:
            print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
