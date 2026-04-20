# Automation Templates (Tool-Agnostic)

This file provides lightweight, machine-readable-friendly templates for Milestone 7 workflows without coupling to any single automation tool export format.

**Source of truth:** [docs/n8n-workflows.md](n8n-workflows.md)  
These templates are supplementary and intentionally generic.

## Why this file exists

- Keep workflow logic portable across n8n, Make, Airflow, GitHub Actions, or scripts.
- Avoid brittle platform-specific JSON exports.
- Preserve stable API contracts and filter rules in one reusable format.

## Global assumptions

- API base URL is provided by runtime config (for example `BIOSI_API_BASE_URL`).
- No API auth header is required in current Milestone 7 state.
- Time-window filters use `created_at` from API response records.
- "Approved Red" means:
  - `review_status == "approved"`
  - `traffic_light == "Red"`

---

## Template 1 — Daily ClinicalTrials.gov ingestion

```yaml
workflow_id: daily-clinicaltrials-ingestion
intent: Run structured ClinicalTrials ingestion once per day and notify result.
trigger:
  type: schedule
  cron_example: "0 7 * * *"
request:
  method: POST
  path: /api/v1/jobs/ingest/clinicaltrials
  headers:
    Accept: application/json
    Content-Type: application/json
  body: {}
expected_response:
  status_code: 200
  required_fields:
    - source
    - studies_seen
    - source_documents_created
    - source_documents_updated
    - events_created
    - events_updated
success_condition:
  all:
    - source == "clinicaltrials.gov"
    - studies_seen >= 0
notification:
  success:
    channel: email_or_slack
    subject: "[Biosi] Daily ClinicalTrials ingestion succeeded"
    body_template: |
      source={source}
      studies_seen={studies_seen}
      source_documents_created={source_documents_created}
      source_documents_updated={source_documents_updated}
      events_created={events_created}
      events_updated={events_updated}
  failure:
    channel: email_or_slack
    subject: "[Biosi] Daily ClinicalTrials ingestion failed"
    body_template: |
      Workflow failed. Check execution logs and API response/error payload.
error_policy:
  on_http_error: notify_and_stop
  on_invalid_payload: notify_and_stop
manual_test:
  - Trigger manually.
  - Verify 200 response and required fields.
  - Verify success notification.
  - Break URL intentionally, verify failure notification.
```

---

## Template 2 — Red event alert (approved Red in last 24h)

```yaml
workflow_id: red-event-alert
intent: Alert analysts when approved Red events exist in the last 24h.
trigger:
  type: schedule
  cron_example: "5 * * * *"
request:
  method: GET
  path: /api/v1/dashboards/recent-events
  query:
    limit: 200
  headers:
    Accept: application/json
expected_response:
  status_code: 200
  item_fields_used:
    - id
    - competitor_name
    - event_type
    - title
    - created_at
    - review_status
    - threat_score
    - traffic_light
filter:
  logic: AND
  conditions:
    - review_status == "approved"
    - traffic_light == "Red"
    - created_at >= now_minus_24h
success_condition:
  filtered_count > 0
notification:
  alert:
    channel: email_or_slack
    subject: "[Biosi] Red approved event alert (last 24h)"
    body_template: |
      count={filtered_count}
      top_items={top_items}
  no_results:
    channel: optional
    subject: "[Biosi] No approved Red events in last 24h"
    body_template: "No qualifying records found."
  failure:
    channel: email_or_slack
    subject: "[Biosi] Red alert workflow failed"
    body_template: |
      Fetch/filter failed. Check execution logs.
error_policy:
  on_http_error: notify_and_stop
  on_filter_error: notify_and_stop
  on_no_results: optional_notify_or_silent_end
manual_test:
  - Trigger manually.
  - Validate fetched item fields.
  - Validate filter keeps only approved+Red+24h.
  - Validate alert message on positive match.
  - Force bad URL to validate failure path.
limitations:
  - recent-events is limit-based; too-low limit may miss qualifying records.
```

---

## Template 3 — Weekly summary digest (approved in last 7d)

```yaml
workflow_id: weekly-summary-digest
intent: Send weekly digest of approved events from last 7 days.
trigger:
  type: schedule
  cron_example: "0 8 * * 1"
request:
  method: GET
  path: /api/v1/dashboards/recent-events
  query:
    limit: 500
  headers:
    Accept: application/json
expected_response:
  status_code: 200
  item_fields_used:
    - competitor_name
    - created_at
    - review_status
    - traffic_light
    - threat_score
filter:
  logic: AND
  conditions:
    - review_status == "approved"
    - created_at >= now_minus_7d
aggregate:
  outputs:
    - approved_total
    - count_by_traffic_light
    - count_by_competitor
    - optional_top_threats
success_condition:
  digest_built == true
notification:
  digest:
    channel: email_or_slack
    subject: "[Biosi] Weekly approved activity digest"
    body_template: |
      approved_total={approved_total}
      by_light={count_by_traffic_light}
      by_competitor={count_by_competitor}
  no_activity:
    channel: optional
    subject: "[Biosi] Weekly digest: no approved activity"
    body_template: "No approved events in the last 7 days."
  failure:
    channel: email_or_slack
    subject: "[Biosi] Weekly digest workflow failed"
    body_template: "Fetch/transform failed. Check execution logs."
error_policy:
  on_http_error: notify_and_stop
  on_aggregation_error: notify_and_stop
  on_no_activity: optional_notify_or_silent_end
manual_test:
  - Trigger manually.
  - Verify filter excludes non-approved or older than 7d.
  - Verify aggregate keys are present.
  - Verify digest notification formatting.
  - Force bad URL to validate failure path.
limitations:
  - Uses recent-events as approximation; no dedicated weekly aggregation endpoint.
  - Digest quality depends on limit covering full 7-day volume.
```

---

## Minimal adapter mapping (optional)

Use this mapping when implementing in a tool:

- `trigger` -> schedule/webhook/manual trigger
- `request` -> HTTP task/operator
- `filter` -> conditional/code/filter step
- `aggregate` -> transform/script/group-by step
- `notification` -> email/slack/ms teams step
- `error_policy` -> error branch/retry/failure handler

This keeps the templates portable while preserving Milestone 7 behavior.
