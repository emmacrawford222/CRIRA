# GCP Architecture (Proposed)

```mermaid
flowchart LR
    A[Cloud Scheduler] --> B[Pub/Sub Trigger]
    B --> C[Cloud Run: CRIRA Pipeline Worker]

    D[Input reviews.json in Cloud Storage] --> C
    C --> E[PII Redaction]
    E --> F[Analysis]
    F --> G[Urgency Routing]
    G --> H[Response Generation]
    H --> I[Human Review Queue Builder]

    I --> J[outputs/*.json in Cloud Storage]
    J --> K[Support Console / CRM Ingestion]

    C --> L[Cloud Logging]
    C --> M[Cloud Monitoring + Alerting]
    C --> N[BigQuery Metrics Sink]

    O[Secret Manager] --> C
```

## Notes
- Secrets are loaded from Secret Manager, never hard-coded.
- Only redacted review text is sent to model-driven stages.
- Human queue output is internal-use and contains recontact details for escalated reviews.
- Rollout: use Cloud Run revisions and weighted traffic for canary model/prompt changes.
