# Biosi n8n Workflows (Milestone 7)

This guide documents the current production n8n workflows and their API dependencies.

## Prerequisites

- Biosi API is running and reachable from n8n.
- n8n account/workspace already exists.
- You know your API base URL, for example:
  - local: `http://127.0.0.1:8000`
  - docker network: `http://web:8000`
- Email or Slack credentials are configured in n8n (for notifications).

## Recommended environment values in n8n

Use n8n environment variables or credentials so URLs are easy to maintain.

```text
BIOSI_API_BASE_URL=http://127.0.0.1:8000
NOTIFY_EMAIL_TO=analyst@yourcompany.com
NOTIFY_EMAIL_FROM=biosi-bot@yourcompany.com
```

---

## System alignment (verified against implementation)

### Scoring model (backend)

`threat_score` is computed with a multi-factor weighted model:

- stage
- competitor tier
- geography
- indication
- confidence

`traffic_light` classification:

- Green: 0–44
- Amber: 45–74
- Red: 75–100

`score_breakdown` is stored for auditability. This replaces earlier single-factor assumptions and reduces Red inflation.

### Intelligence interpretation layer (backend)

Interpretation is factor-based and dynamic (not hardcoded by company/event template), returning:

- `summary`
- `risk_reason`
- `recommended_action`
- `confidence_note`

### Dashboard behavior (backend)

- `top-threats` sorts by `threat_score` then recency.
- `top-threats` deduplicates by competitor (highest-ranked per competitor retained).
- `country` is present in dashboard threat/event payloads.
- No prioritization by ID.

### n8n role

n8n handles orchestration only (scheduling, API calls, delivery) and does not implement scoring/intelligence logic.

---

## Workflow 1 — Biosi Intelligence Pipeline

### Purpose

Daily orchestration to health-check backend, run ingestion, and trigger alerts when Red threats exist.

### Trigger

- Schedule Trigger (example: daily 07:00 local)

### Exact API endpoints used

1. `GET /api/v1/health/n8n`
2. `POST /api/v1/jobs/ingest/clinicaltrials`
3. `GET /api/v1/dashboards/top-threats`

### Key parameters

- `limit` on top-threats (typical `10`)
- `approved_only` on top-threats (ops choice, default backend value is `false`)

### Data flow

1. Health check gate.
2. ClinicalTrials ingestion call.
3. Backend ingests and performs scoring (`threat_score`, `traffic_light`, `score_breakdown`).
4. Pipeline fetches top threats and checks for Red records.
5. If Red exists, invoke Red Alert workflow.
6. Failure branch sends notification.

### Dependencies on backend logic

- Ingestion/scoring/interpretation are backend-owned.
- Red alert trigger quality depends on backend classification.

### Known limitations

- No `traffic_light` query filter on `top-threats`; filtering is done in n8n.
- Limit-based fetch can exclude lower-ranked threats.

---

## Workflow 2 — Red Alert Notification

### Purpose

Alert on approved Red events from the recent-event feed.

### Trigger

- Schedule Trigger (example: hourly minute 05)

### Exact API endpoints used

1. `GET /api/v1/dashboards/recent-events`

### Key parameters

- `limit` (1..100, typical 100)
- `since_hours=24` (recommended)

### Data flow

1. Request recent events with server-side window (`since_hours=24`).
2. In n8n, filter to:
   - `review_status == "approved"`
   - `traffic_light == "Red"`
3. If count > 0, send alert.
4. Else end quietly (or optional no-results heartbeat).

### Dependencies on backend logic

- Red detection relies on backend `traffic_light` classification.
- Endpoint payload includes `country` for region-aware alert context.

### Known limitations

- No dedicated Red-alert endpoint; workflow is feed + filter.
- Still limit-sensitive at high volume.

---

## Workflow 3 — Press Release Ingestion

### Purpose

Ingest unstructured press releases and persist scored event records.

### Trigger

- Webhook/manual ingestion trigger from n8n source collector

### Exact API endpoints used

1. `POST /api/v1/jobs/ingest/press-release`
2. Optional follow-up reads for alerts/reporting:
   - `GET /api/v1/dashboards/top-threats`
   - `GET /api/v1/intelligence/weekly-digest-v2`

### Key parameters

Press-release ingestion request body:

```json
{
  "text": "<press release text>",
  "source_url": "https://example.com/press-release/..."
}
```

### Data flow

1. n8n posts raw text.
2. Backend performs LLM extraction.
3. Backend upserts source document + event.
4. Backend applies scoring and stores `score_breakdown`.
5. n8n optionally checks threat/intelligence endpoints for notification decisions.

### Dependencies on backend logic

- LLM extraction is backend-owned.
- Scoring and interpretation are backend-owned outputs consumed by n8n.

### Known limitations

- Ingestion response is operational (created/updated + extracted payload), not a full intelligence digest.

---

## Workflow 4 — Weekly Intelligence Digest

### Purpose

Send weekly analyst digest using backend dashboard/intelligence outputs.

### Trigger

- Schedule Trigger (example: Monday 08:00 local)

### Exact API endpoints used (current workflow pattern)

1. `GET /api/v1/dashboards/summary`
2. `GET /api/v1/dashboards/recent-events`
3. `GET /api/v1/dashboards/top-threats`
4. `GET /api/v1/dashboards/review-queue`

### Key parameters

- `recent-events.limit` (typical 20)
- `recent-events.since_days=7`
- `top-threats.limit` (typical 5)
- `top-threats.approved_only` as required by ops policy

### Data flow

1. Fetch dashboard slices.
2. Compose weekly digest in n8n.
3. Deliver email.

### Dependencies on backend logic

- Sorting/dedupe/country availability come from backend dashboard services.
- Interpretation can be consumed from backend endpoint when weekly flow is upgraded.

### Known limitations

- Current dashboard-based weekly digest is still limit-based.
- No unbounded backend weekly rollup endpoint for all historical events.

### Interpretation-capable endpoint (available)

- `GET /api/v1/intelligence/weekly-digest-v2?limit=100&approved_only=<bool>`
- Returns `summary`, `risk_reason`, `recommended_action`, and `score_breakdown` from backend interpretation.

---

## 🧠 Intelligence Layer (NEW)

Scoring and interpretation are intentionally separated:

- Scoring: quantitative risk (`threat_score`, `traffic_light`, `score_breakdown`)
- Interpretation: decision language (`summary`, `risk_reason`, `recommended_action`, `confidence_note`)

This design keeps n8n free of intelligence logic, while preserving auditability via `score_breakdown`.

---

## 🔗 Backend vs n8n Responsibilities

### n8n

- Triggering/scheduling
- API orchestration
- Routing/notification delivery

### Backend

- Ingestion normalization/extraction
- Multi-factor scoring
- Traffic-light classification
- Intelligence interpretation
- Dashboard ranking/deduplication payload shaping

---

## Quick validation checklist (before enabling schedules)

- [ ] API base URL is reachable from n8n.
- [ ] All HTTP nodes return JSON successfully.
- [ ] Approved/Red and time-window filters are validated with real data.
- [ ] Success and failure notifications are both tested.
- [ ] Optional no-results/no-activity behavior is intentionally chosen.
- [ ] Schedules are enabled only after manual tests pass.


---

## Workflow 5 — Email Intelligence Digest (Milestone 8)

### Purpose

Send department-specific or generic intelligence briefings via email using the backend `generate-briefings` endpoint.

### Trigger

- Schedule Trigger (example: Monday 08:00 local for weekly; daily 07:00 for daily)
- Optional: Webhook trigger for on-demand briefings

### Exact API endpoints used

1. `GET /api/v1/health` (DB-verified health check)
2. `POST /api/v1/intelligence/generate-briefings?department={dept}`
3. Optional: `GET /api/v1/dashboards/summary` for header stats

### Key parameters

- `department` (required): `regulatory` | `commercial` | `medical_affairs` | `market_access`
- `limit` (1..100, typical 50)
- `approved_only` (ops policy choice)

### Data flow

1. Health check gate (`GET /api/v1/health`).
2. Call `generate-briefings` for each configured department (or once for generic).
3. Backend returns structured JSON:
   - `executive_summary`
   - `market_sections[]`
   - `event_cards[]`
   - `milestones[]`
4. n8n maps the JSON into an HTML email template.
5. Email is routed based on `department` + `region` (see Regional Routing below).
6. Failure branch sends alert to ops channel.

### Workflow JSON (simplified n8n node structure)

```json
{
  "name": "Biosi Email Intelligence Digest",
  "nodes": [
    {
      "type": "n8n-nodes-base.scheduleTrigger",
      "name": "Weekly Schedule",
      "parameters": { "rule": { "interval": [{ "field": "weeks", "value": 1 }] } }
    },
    {
      "type": "n8n-nodes-base.httpRequest",
      "name": "Health Check",
      "parameters": {
        "method": "GET",
        "url": "={{ $env.BIOSI_API_BASE_URL }}/api/v1/health"
      }
    },
    {
      "type": "n8n-nodes-base.httpRequest",
      "name": "Generate Briefing",
      "parameters": {
        "method": "POST",
        "url": "={{ $env.BIOSI_API_BASE_URL }}/api/v1/intelligence/generate-briefings",
        "sendQuery": true,
        "queryParameters": {
          "parameters": [
            { "name": "department", "value": "={{ $json.department }}" },
            { "name": "limit", "value": "50" },
            { "name": "approved_only", "value": "false" }
          ]
        }
      }
    },
    {
      "type": "n8n-nodes-base.code",
      "name": "Build HTML Email",
      "parameters": {
        "jsCode": "// See HTML Email Format section below\nreturn items;"
      }
    },
    {
      "type": "n8n-nodes-base.emailSend",
      "name": "Send Email",
      "parameters": {
        "toEmail": "={{ $json.recipient_email }}",
        "subject": "={{ $json.subject }}",
        "html": "={{ $json.html_body }}"
      }
    }
  ]
}
```

### HTML Email Format

The email template consumes `generate-briefings` JSON and produces a responsive HTML layout.

**Required template variables:**

| Variable | Source JSON field |
|---|---|
| `{{ executive_summary }}` | `executive_summary` |
| `{{ department }}` | `department` |
| `{{ generated_at }}` | `generated_at` |
| `{{ red_count }}` | Count of `event_cards` where `traffic_light == "Red"` |
| `{{ amber_count }}` | Count of `event_cards` where `traffic_light == "Amber"` |
| `{{ event_cards }}` | Array of `event_cards` |
| `{{ market_sections }}` | Array of `market_sections` |
| `{{ milestones }}` | Array of `milestones` |

**HTML structure (simplified):**

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    .red { color: #c0392b; }
    .amber { color: #e67e22; }
    .green { color: #27ae60; }
    .card { border-left: 4px solid #ccc; padding: 12px; margin: 8px 0; }
    .card.red { border-left-color: #c0392b; }
  </style>
</head>
<body>
  <h1>{{ department | title }} Intelligence Briefing</h1>
  <p><strong>Generated:</strong> {{ generated_at }}</p>
  <p class="summary">{{ executive_summary }}</p>

  <h2>Threat Overview</h2>
  <p>🔴 {{ red_count }} Red &nbsp; 🟠 {{ amber_count }} Amber</p>

  <h2>Key Events</h2>
  {% for card in event_cards %}
  <div class="card {{ card.traffic_light | lower }}">
    <strong>{{ card.competitor_name }}</strong> — {{ card.title }}<br>
    <span class="score">Score: {{ card.threat_score }}</span><br>
    <em>{{ card.department_frame }}</em><br>
    {% if card.recommended_action %}
    <small>Action: {{ card.recommended_action }}</small>
    {% endif %}
  </div>
  {% endfor %}

  <h2>Upcoming Milestones</h2>
  <ul>
    {% for m in milestones %}
    <li><strong>{{ m.date }}</strong> — {{ m.competitor_name }}: {{ m.title }} ({{ m.priority }})</li>
    {% endfor %}
  </ul>

  <hr>
  <small>Automated by Biosi Intelligence Platform</small>
</body>
</html>
```

> **Note:** n8n's native `Email Send` node supports HTML bodies directly. If using a custom SMTP node, ensure `Content-Type: text/html; charset=utf-8` is set.

### Regional Routing Logic

Route emails to different distribution lists based on event geography concentration:

| Rule | Recipient List | Condition |
|---|---|---|
| **NA Priority** | `na-team@company.com` | ≥ 40% of Red events have `country == "United States"` or `region == "North America"` |
| **EU Priority** | `eu-team@company.com` | ≥ 40% of Red events have `region == "Europe"` |
| **APAC Priority** | `apac-team@company.com` | ≥ 40% of Red events have `region == "Asia-Pacific"` |
| **Global Default** | `global-ci@company.com` | No region dominates; or generic briefing |

**n8n routing node (Code node):**

```javascript
const cards = $input.first().json.event_cards || [];
const redCards = cards.filter(c => c.traffic_light === 'Red');

function regionOf(card) {
  const meta = card.metadata_json || {};
  return (meta.region || '').toLowerCase();
}

const naCount = redCards.filter(c => regionOf(c).includes('north america')).length;
const euCount = redCards.filter(c => regionOf(c).includes('europe')).length;
const apacCount = redCards.filter(c => regionOf(c).includes('asia')).length;
const totalRed = redCards.length || 1;

let recipient = 'global-ci@company.com';
if (naCount / totalRed >= 0.4) recipient = 'na-team@company.com';
else if (euCount / totalRed >= 0.4) recipient = 'eu-team@company.com';
else if (apacCount / totalRed >= 0.4) recipient = 'apac-team@company.com';

return [{ json: { ...$input.first().json, recipient_email: recipient } }];
```

### Dependencies on backend logic

- `generate-briefings` owns all department framing, market sections, and event cards.
- n8n owns template rendering, routing logic, and delivery only.

### Known limitations

- Email size grows linearly with `limit`; recommend `limit <= 50` for email workflows.
- No image/chart generation; plain HTML only.
- Regional routing is heuristic-based (40% threshold); tune per ops feedback.

---

## Updated Endpoint Inventory

| Endpoint | Method | Used By |
|---|---|---|
| `GET /api/v1/health` | GET | WF1, WF5 |
| `GET /api/v1/health/n8n` | GET | WF1 (legacy) |
| `POST /api/v1/jobs/ingest/clinicaltrials` | POST | WF1 |
| `POST /api/v1/jobs/ingest/press-release` | POST | WF3 |
| `POST /api/v1/jobs/recompute-scores` | POST | Manual / scheduled ops |
| `GET /api/v1/dashboards/top-threats` | GET | WF1, WF4 |
| `GET /api/v1/dashboards/recent-events` | GET | WF2, WF4 |
| `GET /api/v1/dashboards/summary` | GET | WF4, WF5 |
| `GET /api/v1/dashboards/review-queue` | GET | WF4 |
| `GET /api/v1/intelligence/digest` | GET | WF4 (legacy) |
| `GET /api/v1/intelligence/weekly-digest-v2` | GET | WF3 (optional) |
| `POST /api/v1/intelligence/generate-briefings` | POST | WF5 |
