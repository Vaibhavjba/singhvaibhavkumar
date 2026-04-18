#!/usr/bin/env python3
"""
arcgis-k8s-event-report.py

Pulls Kubernetes events from a namespace, groups them by severity (Warning / Normal)
and reason (OOMKilled, BackOff, Pulling, etc.), and outputs a human-readable or
JSON summary. ArcGIS-component-aware: labels events by GIS component group.

CI behaviour: exits 1 when Warning events are found, 0 when the namespace is clean.

Usage:
    python arcgis-k8s-event-report.py --namespace arcgis --since-minutes 60
    python arcgis-k8s-event-report.py --namespace arcgis --since-minutes 30 --output json
    python arcgis-k8s-event-report.py --namespace arcgis --since-minutes 60 --in-cluster

Requirements:
    pip install kubernetes
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException

# ── ArcGIS component classification (same as readiness check) ───────────────
COMPONENT_PATTERNS: dict[str, list[str]] = {
    "portal":    ["arcgis-portal", "arcgis-enterprisegis"],
    "ingress":   ["arcgis-ingress", "arcgis-nginx"],
    "raster":    ["arcgis-rasterserver", "arcgis-rasteranalyticsmanager"],
    "notebook":  ["arcgis-notebook"],
    "upgrader":  ["arcgis-upgrader"],
    "datastore": ["arcgis-datastore", "arcgis-relationalstore", "arcgis-objectstore"],
    "routing":   ["arcgis-route", "arcgis-network"],
}

# Reasons that usually signal real problems (surface prominently)
CRITICAL_REASONS = {
    "OOMKilled", "BackOff", "CrashLoopBackOff", "Failed",
    "FailedScheduling", "FailedMount", "FailedAttachVolume",
    "Unhealthy", "NodeNotReady", "Evicted",
}


def classify(object_name: str) -> str:
    for group, patterns in COMPONENT_PATTERNS.items():
        if any(p in object_name for p in patterns):
            return group
    return "other"


def aware_dt(dt) -> datetime:
    """Ensure a datetime is timezone-aware (UTC)."""
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_events(namespace: str, since_minutes: int) -> list[dict]:
    v1 = client.CoreV1Api()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)

    try:
        event_list = v1.list_namespaced_event(namespace)
    except ApiException as e:
        print(f"ERROR  Could not list events in namespace '{namespace}': {e.reason}")
        sys.exit(2)

    events = []
    for ev in event_list.items:
        # Use last_timestamp or event_time, whichever is set
        ts = aware_dt(ev.last_timestamp or ev.event_time)
        if ts < cutoff:
            continue

        obj_name = ev.involved_object.name or ""
        events.append({
            "type":      ev.type or "Unknown",
            "reason":    ev.reason or "Unknown",
            "object":    obj_name,
            "component": classify(obj_name),
            "message":   (ev.message or "").strip(),
            "count":     ev.count or 1,
            "timestamp": ts.isoformat(),
            "critical":  (ev.reason or "") in CRITICAL_REASONS,
        })

    # Sort: warnings first, then by count descending
    events.sort(key=lambda e: (e["type"] != "Warning", -e["count"]))
    return events


def print_table(events: list[dict], namespace: str, since_minutes: int) -> bool:
    warnings = [e for e in events if e["type"] == "Warning"]
    normals  = [e for e in events if e["type"] == "Normal"]

    print(f"\nNamespace : {namespace}")
    print(f"Window    : last {since_minutes} minutes")
    print(f"Events    : {len(warnings)} Warning(s)  |  {len(normals)} Normal(s)")

    if warnings:
        print("\n⚠️  WARNINGS")
        # Group by component for readability
        by_component: dict[str, list] = defaultdict(list)
        for e in warnings:
            by_component[e["component"]].append(e)

        for comp in sorted(by_component):
            print(f"\n  [{comp.upper()}]")
            for e in by_component[comp]:
                flag = " 🔴" if e["critical"] else ""
                msg  = e["message"][:90] + "…" if len(e["message"]) > 90 else e["message"]
                print(f"    [{e['count']:3d}x] {e['reason']:25s} {e['object']}")
                print(f"           {msg}{flag}")

    if not warnings:
        print("\n✅ No Warning events in the last {since_minutes} minutes.\n".format(since_minutes=since_minutes))

    return len(warnings) == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ArcGIS K8s namespace event report — grouped by component and severity"
    )
    parser.add_argument("--namespace",     default="arcgis",
                        help="Kubernetes namespace to inspect (default: arcgis)")
    parser.add_argument("--since-minutes", type=int, default=60,
                        help="Look back this many minutes (default: 60)")
    parser.add_argument("--kubeconfig",    default=None,
                        help="Path to kubeconfig file")
    parser.add_argument("--in-cluster",    action="store_true",
                        help="Use in-cluster service account credentials")
    parser.add_argument("--output", choices=["table", "json"], default="table")
    args = parser.parse_args()

    if args.in_cluster:
        k8s_config.load_incluster_config()
    else:
        k8s_config.load_kube_config(config_file=args.kubeconfig)

    events = get_events(args.namespace, args.since_minutes)

    if args.output == "json":
        summary = {
            "namespace":     args.namespace,
            "since_minutes": args.since_minutes,
            "total":         len(events),
            "warnings":      sum(1 for e in events if e["type"] == "Warning"),
            "normals":       sum(1 for e in events if e["type"] == "Normal"),
            "events":        events,
        }
        print(json.dumps(summary, indent=2))
        sys.exit(0 if summary["warnings"] == 0 else 1)

    clean = print_table(events, args.namespace, args.since_minutes)
    sys.exit(0 if clean else 1)


if __name__ == "__main__":
    main()
