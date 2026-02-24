# Integration Tests

This directory contains the full integration test suite for `firestore-pydantic-odm`.
Unlike the unit tests in `tests/` (which use `MagicMock`), these tests run against a
**real Firestore backend** and validate that data actually persists, queries return
correct results, and the ODM behaves identically to the raw Firestore SDK.

---

## Test Files

| File | Tests | What it covers |
|------|------:|----------------|
| `test_crud_emulator.py` | 15 | Create, read, update, delete, exists — top-level documents |
| `test_queries_emulator.py` | 22 | Filters (`==`, `!=`, `>`, `in`, `array_contains`), ordering, limit, offset, count |
| `test_subcollections_emulator.py` | 18 | Subcollection hierarchy, cascade delete, accessor pattern, collection group |
| `test_batch_emulator.py` | 7 | Batch create / update / delete, mixed operations, auto-ID, 500-op limit |
| `test_sdk_validation.py` | 9 | Cross-validation: every operation verified via both ODM and raw SDK |
| **Total** | **71** | |

---

## Backend Detection

The `conftest.py` auto-detects which backend to use based on environment variables:

| Variable | Emulator mode | Real Firestore mode |
|----------|:-------------:|:-------------------:|
| `FIRESTORE_EMULATOR_HOST` | `localhost:8080` | *(unset or empty)* |
| `GOOGLE_CLOUD_PROJECT` | `test-project` | your GCP project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | *(not needed)* | path to SA JSON key |
| `DATABASE` | *(not needed)* | named Firestore database |
| `BATCH_LIMIT_TEST_SIZE` | `500` (default) | `50` (saves free-tier quota) |

---

## Running Locally

### Against the Emulator

```bash
# Start the emulator
docker compose -f docker-compose.test.yml up -d

# Run only integration tests
FIRESTORE_EMULATOR_HOST=localhost:8080 pytest tests/integration/ -v

# Run the full suite (unit + integration)
FIRESTORE_EMULATOR_HOST=localhost:8080 pytest tests/ -v

# Stop the emulator
docker compose -f docker-compose.test.yml down
```

### Against Real Firestore

```bash
GOOGLE_APPLICATION_CREDENTIALS=./sa.json \
GOOGLE_CLOUD_PROJECT=real-project \
DATABASE=databasename \
BATCH_LIMIT_TEST_SIZE=50 \
pytest tests/integration/ -v --tb=short
```

---

## CI / CD Workflow

```mermaid
%%{init: {"flowchart": {"htmlLabels": false}} }%%
flowchart TD
    classDef secret  fill:#7c3aed,color:#fff,stroke:#5b21b6
    classDef real    fill:#d97706,color:#fff,stroke:#92400e
    classDef gate    fill:#1a56db,color:#fff,stroke:#1e40af
    classDef publish fill:#dc2626,color:#fff,stroke:#991b1b
    classDef mock    fill:#374151,color:#fff,stroke:#111827

    subgraph SECRETS["GitHub Secrets"]
        direction LR
        S1["`**GCP_SA_KEY**
        base64 -w0 sa-key.json`"]
        S2["`**GCP_PROJECT_ID**
        e.g. optical-order-346900`"]
        S3["`**GCP_DATABASE**
        e.g. firestore-pydantic-dm`"]
        S4["`**RELEASE_PAT**
        Personal Access Token`"]
        S5["`**PIPL_TOKEN**
        PyPI API token`"]
    end

    DEV["Developer opens Pull Request"]
    DEV --> TY["test.yml — on: pull_request"]

    subgraph TESTYML["test.yml — runs on EVERY PR"]
        direction TB
        TY --> TM["`Matrix: 11 jobs
        Py 3.9 / 3.10 / 3.11 / 3.12
        x Pydantic V1 / V2 / V2.11+`"]
        TM --> TE["`docker run -d
        Firestore Emulator :8080
        no credentials needed`"]
        TE --> TU["`Unit tests
        pytest tests/ --ignore=integration`"]
        TE --> TI["`Integration tests
        FIRESTORE_EMULATOR_HOST=localhost:8080
        GOOGLE_CLOUD_PROJECT=test-project`"]
        TU --> TG["test-gate — all 11 jobs passed"]
        TI --> TG
    end

    TG -->|"PR can be merged"| MERGE["PR merged to master"]
    MERGE --> RY["release.yml — on: PR closed + merged"]

    subgraph RELEASEYML["release.yml — runs on MERGE to master"]
        direction TB
        RY --> RM["`Matrix: 11 jobs
        same combination`"]
        RM --> RC["`Decode GCP_SA_KEY
        base64 -d > /tmp/sa-key.json`"]
        RC --> S1
        RC --> S2
        RC --> S3
        RC --> RU["`Unit tests
        pytest tests/ --ignore=integration`"]
        RC --> RI["`Integration tests — Real Firestore
        GOOGLE_APPLICATION_CREDENTIALS
        GOOGLE_CLOUD_PROJECT
        DATABASE
        BATCH_LIMIT_TEST_SIZE=50`"]
        RU --> RG["release-gate — all 11 jobs passed"]
        RI --> RG
        RG --> VB["`Version bump
        setup.py + commit + tag`"]
        S4 --> VB
    end

    VB -->|"push tag vX.Y.Z"| PY["publish.yml — on: push tag v*"]

    subgraph PUBLISHYML["publish.yml — runs on TAG push"]
        direction TB
        PY --> PB["python -m build"]
        PB --> PP["`pypa/gh-action-pypi-publish
        using PIPL_TOKEN`"]
        S5 --> PP
    end

    PP --> PYPI[("PyPI — new version published")]

    class S1,S2,S3,S4,S5 secret
    class TE,TI mock
    class RC,RI real
    class TG,RG gate
    class PP,PYPI publish
```

---

## GitHub Secrets Reference

| Secret | How to generate | Used in |
|--------|-----------------|---------|
| `GCP_SA_KEY` | `base64 -w0 sa-key.json` | `release.yml` — authenticates to real Firestore |
| `GCP_PROJECT_ID` | Your GCP project ID string | `release.yml` |
| `GCP_DATABASE` | Named Firestore database (omit for default) | `release.yml` |
| `RELEASE_PAT` | GitHub PAT with `repo` scope | `release.yml` — pushes version bump commit |
| `PIPL_TOKEN` | PyPI API token | `publish.yml` — publishes to PyPI |

---

## Dual-Layer Validation

Every integration test validates operations **twice**: once through the ODM, once through
the raw `AsyncClient`. This ensures the ODM is not hiding data corruption or silent failures.

```
Phase 1 — Write via ODM    ->  user = User(name="Alice"); await user.save()
Phase 2 — Verify via SDK   ->  doc = await client.collection("users").document(id).get()
                               assert doc.to_dict()["name"] == "Alice"

Phase 3 — Write via SDK    ->  await client.collection("users").document("x").set({...})
Phase 4 — Read via ODM     ->  result = await User.get("x")
                               assert result.name == ...
```

---

## Data Cleanup

| Backend | Method | Speed |
|---------|--------|-------|
| Emulator | `DELETE http://{host}/emulator/v1/projects/{project}/databases/(default)/documents` | ~5 ms |
| Real Firestore | Recursive batch delete on known test collections (`users`, `products`) | ~200 ms |

Cleanup runs **after each test** via the `clean_firestore` autouse fixture, guaranteeing full isolation.
