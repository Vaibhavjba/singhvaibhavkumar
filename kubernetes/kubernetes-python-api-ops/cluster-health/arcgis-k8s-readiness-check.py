#!/usr/bin/env python3
"""
arcgis-k8s-readiness-check.py

Reports ArcGIS Enterprise pod health grouped by component (portal, ingress,
raster, notebook, upgrader, datastore). Designed to run in CI/CD pipelines:
exits 0 when all pods are ready, 1 when any pod is not ready.

Usage:
    # Against a kubeconfig (local / CI):
    python arcgis-k8s-readiness-check.py --namespace arcgis --kubeconfig ~/.kube/config

    # Inside the cluster (service-account token):
    python arcgis-k8s-readiness-check.py --namespace arcgis --in-cluster

    # JSON output for downstream parsing:
    python arcgis-k8s-readiness-check.py --namespace arcgis --output json

Requirements:
    pip install kubernetes
"""

import argparse
import json
import sys
import logging

from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException

logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")

# ── Component classification ────────────────────────────────────────────────
COMPONENT_PATTERNS: dict[str, list[str]] = {
    "portal":    ["arcgis-portal", "arcgis-enterprisegis"],
    "ingress":   ["arcgis-ingress", "arcgis-nginx"],
    "raster":    ["arcgis-rasterserver", "arcgis-rasteranalyticsmanager"],
    "notebook":  ["arcgis-notebook"],
    "upgrader":  ["arcgis-upgrader"],
    "datastore": ["arcgis-datastore", "arcgis-relationalstore", "arcgis-objectstore"],
    "routing":   ["arcgis-route", "arcgis-network"],
}


def classify(pod_name: str) -> str:
    for group, patterns in COMPONENT_PATTERNS.items():
        if any(p in pod_name for p in patterns):
            return group
    return "other"


# ── Core check ──────────────────────────────────────────────────────────────
def check_namespace(namespace: str) -> dict[str, list[dict]]:
    """Return pod health grouped by ArcGIS component."""
    v1 = client.CoreV1Api()
    try:
        pod_list = v1.list_namespaced_pod(namespace)
    except ApiException as e:
        print(f"ERROR  Could not list pods in namespace '{namespace}': {e.reason}")
        sys.exit(2)

    groups: dict[str, list[dict]] = {}
    for pod in pod_list.items:
        name  = pod.metadata.name
        phase = pod.status.phase or "Unknown"

        container_statuses = pod.status.container_statuses or []
        all_ready = all(cs.ready for cs in container_statuses) and bool(container_statuses)

        # Surface CrashLoopBackOff / OOMKilled reason if present
        reason = phase
        for cs in container_statuses:
            if cs.state and cs.state.waiting and cs.state.waiting.reason:
                reason = cs.state.waiting.reason
                break
            if cs.last_state and cs.last_state.terminated and cs.last_state.terminated.reason:
                reason = cs.last_state.terminated.reason

        group = classify(name)
        groups.setdefault(group, []).append({
            "name":    name,
            "phase":   phase,
            "reason":  reason,
            "ready":   all_ready,
        })

    return groups


# ── Output formatters ────────────────────────────────────────────────────────
def print_table(groups: dict[str, list[dict]]) -> bool:
    all_healthy = True
    for group in sorted(groups):
        print(f"\n[{group.upper()}]")
        for pod in groups[group]:
            symbol = "✅ READY    " if pod["ready"] else "❌ NOT READY"
            extra  = f"  ({pod['reason']})" if pod["reason"] != pod["phase"] else f"  ({pod['phase']})"
            print(f"  {symbol}  {pod['name']}{extra}")
            if not pod["ready"]:
                all_healthy = False
    return all_healthy


def print_json(groups: dict[str, list[dict]]) -> bool:
    all_healthy = all(
        pod["ready"]
        for pods in groups.values()
        for pod in pods
    )
    output = {
        "all_healthy": all_healthy,
        "components":  groups,
    }
    print(json.dumps(output, indent=2))
    return all_healthy


# ── Entry point ──────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="ArcGIS Enterprise K8s readiness check — grouped by component"
    )
    parser.add_argument("--namespace",  default="arcgis",
                        help="Kubernetes namespace to inspect (default: arcgis)")
    parser.add_argument("--kubeconfig", default=None,
                        help="Path to kubeconfig file (default: $KUBECONFIG or ~/.kube/config)")
    parser.add_argument("--in-cluster", action="store_true",
                        help="Use in-cluster service account credentials")
    parser.add_argument("--output", choices=["table", "json"], default="table",
                        help="Output format (default: table)")
    args = parser.parse_args()

    # Load kubeconfig
    if args.in_cluster:
        k8s_config.load_incluster_config()
    else:
        k8s_config.load_kube_config(config_file=args.kubeconfig)

    groups = check_namespace(args.namespace)

    if not groups:
        print(f"No pods found in namespace '{args.namespace}'.")
        sys.exit(2)

    if args.output == "json":
        healthy = print_json(groups)
    else:
        total = sum(len(v) for v in groups.values())
        ready = sum(1 for pods in groups.values() for p in pods if p["ready"])
        print(f"Namespace: {args.namespace}  |  Pods: {ready}/{total} ready")
        healthy = print_table(groups)
        print()

    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
