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
    H --> P{Route}
    P -->|human_review| Q[Immediate internal queue handoff]
    P -->|llm_response + positive| R[Cloud Tasks delayed dispatch]
    R --> S[Cloud Run Response Delivery Worker]

    C --> L[Cloud Logging]
    C --> M[Cloud Monitoring + Alerting]
    C --> N[BigQuery Metrics Sink]
    S --> L
    S --> M

    O[Secret Manager] --> C

    T[Cloud Run Revision N-1] --> U[Weighted traffic split]
    V[Cloud Run Revision N] --> U
```

## Notes
- Secrets are loaded from Secret Manager, never hard-coded.
- Only redacted review text is sent to model-driven stages.
- Human queue output is internal-use and contains recontact details for escalated reviews.
- Positive non-urgent responses can be dispatched with a short delay via Cloud Tasks.
- Rollout: use Cloud Run revisions and weighted traffic for canary model/prompt changes.
- Observability should include per-stage latency, fallback/error rates, dispatch delay backlog, and cost-per-1000 reviews.
