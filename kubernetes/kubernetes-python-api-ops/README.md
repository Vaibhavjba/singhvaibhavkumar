# Kubernetes Python API Ops

Python scripts for managing and monitoring ArcGIS Enterprise on Kubernetes — pod health checks, namespace event reports, and workload validation. All scripts are CI/CD-friendly: structured JSON output, explicit exit codes, and support for both kubeconfig and in-cluster auth.

---

## Scripts

### `cluster-health/arcgis-k8s-readiness-check.py`

**Problem it solves:** After an ArcGIS Enterprise upgrade or pod restart event on Kubernetes, operators need to quickly confirm all components are ready before routing traffic or marking a deployment successful. Scanning `kubectl get pods` output manually across dozens of pods is slow and doesn't group results by GIS component. This script groups pods by component (portal, ingress, raster, notebook, upgrader, datastore), surfaces `CrashLoopBackOff` / `OOMKilled` reasons inline, and exits non-zero if anything is not ready — making it a drop-in CI gate.

**Exit codes:** `0` all pods ready · `1` one or more pods not ready · `2` API/namespace error

**Install:**
```bash
pip install kubernetes
```

**Run:**
```bash
# Against a kubeconfig (local or CI)
python cluster-health/arcgis-k8s-readiness-check.py \
  --namespace arcgis \
  --kubeconfig ~/.kube/config

# Inside the cluster (service-account token)
python cluster-health/arcgis-k8s-readiness-check.py \
  --namespace arcgis \
  --in-cluster

# JSON output for downstream pipeline steps
python cluster-health/arcgis-k8s-readiness-check.py \
  --namespace arcgis \
  --output json
```

---

### `namespace-reports/arcgis-k8s-event-report.py`

**Problem it solves:** Kubernetes Warning events (`OOMKilled`, `BackOff`, `CrashLoopBackOff`, `FailedMount`, etc.) are the earliest signal that something is wrong with a deployment — but they scroll off `kubectl get events` quickly and aren't grouped by GIS component. During and after ArcGIS Enterprise upgrades, engineers need a timestamped, component-grouped view of Warning events over a configurable window (e.g. last 60 minutes) to identify which component triggered the problem. This script provides that view and exits `1` if any Warning events are found — enabling automated regression detection in CI pipelines.

**Exit codes:** `0` no Warning events · `1` one or more Warning events found · `2` API/namespace error

**Install:**
```bash
pip install kubernetes
```

**Run:**
```bash
# Table view — last 60 minutes of events
python namespace-reports/arcgis-k8s-event-report.py \
  --namespace arcgis \
  --since-minutes 60

# Shorter window during active upgrade
python namespace-reports/arcgis-k8s-event-report.py \
  --namespace arcgis \
  --since-minutes 30

# JSON output for pipeline consumption
python namespace-reports/arcgis-k8s-event-report.py \
  --namespace arcgis \
  --since-minutes 60 \
  --output json

# In-cluster (e.g. running as a Job inside the cluster)
python namespace-reports/arcgis-k8s-event-report.py \
  --namespace arcgis \
  --since-minutes 60 \
  --in-cluster
```