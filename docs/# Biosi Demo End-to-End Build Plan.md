#   
# Biosi Demo End-to-End Build Plan  
  
## Objective  
  
Build a non-Microsoft MVP for a Biosimilar Competitive Intelligence tool focused on Opdivo (nivolumab). The MVP must ingest public biosimilar-related data, normalize it into structured events, score event risk, support human review, and expose data through API endpoints and automation-ready workflows. The first structured source must be ClinicalTrials.gov API v2 because it is official and provides modern structured JSON data.[cite:70][cite:79][cite:101]  
  
## Stack  
  
Use this stack exactly unless there is a strong implementation reason to adjust:  
  
- Backend: FastAPI  
- ORM: SQLAlchemy  
- Database: Neon PostgreSQL  
- Migrations: Alembic  
- HTTP client: httpx  
- AI extraction: OpenRouter  
- Workflow automation: n8n  
- Runtime: Docker Compose  
- Version control: GitHub  
  
Use Neon pooled connection for app runtime and Neon direct connection for migrations and admin tasks, because pooled transaction-mode connections are not suitable for every operation.[cite:146][cite:152]  
  
## Product Scope  
  
### In scope  
- FastAPI backend  
- Neon PostgreSQL database  
- ClinicalTrials.gov API ingestion  
- OpenRouter extraction for one unstructured source path  
- Event normalization  
- Threat scoring  
- Human review workflow  
- Dashboard-ready API summary endpoints  
- n8n workflows for ingestion and alerts  
  
### Out of scope  
- Full authentication  
- Full frontend app  
- Patent analytics  
- Multi-molecule portfolio support  
- Enterprise observability stack  
- Forecasting models  
- Tender scraping  
  
## Success Criteria  
  
The MVP is complete when:  
1. The app runs locally with Docker Compose.  
2. FastAPI health endpoint works.  
3. Neon connection works.  
4. Alembic migrations run successfully using the direct Neon connection.[cite:146][cite:152]  
5. ClinicalTrials.gov ingestion stores at least one raw source payload and one normalized event.[cite:70][cite:79]  
6. OpenRouter extraction converts one sample unstructured text into a structured event.[cite:129][cite:162]  
7. Each event receives a threat score and traffic light.  
8. Events can be approved or rejected via review endpoints.  
9. n8n can trigger ingestion and send a test notification.[cite:180][cite:183]  
10. Seed data supports a 5-minute demo.  
  
## Architecture Principles  
  
- Keep route handlers thin.  
- Keep business logic in services.  
- Keep database writes in repositories where practical.[cite:105][cite:111][cite:113]  
- Store raw source payloads before normalization for auditability.[cite:51]  
- Use deterministic parsing for structured sources before AI extraction.[cite:70][cite:79][cite:82]  
- Make the LLM provider swappable via one internal adapter interface.[cite:129][cite:162]  
- Prefer explicit and testable code over abstraction-heavy patterns.  
  
## Folder Structure  
  
Create the project with this structure:  
  
```text  
biosi/  
├── app/  
│   ├── main.py  
│   ├── core/  
│   │   ├── config.py  
│   │   ├── database.py  
│   │   ├── logging.py  
│   │   └── security.py  
│   ├── api/  
│   │   ├── deps.py  
│   │   └── v1/  
│   │       ├── health.py  
│   │       ├── events.py  
│   │       ├── competitors.py  
│   │       ├── sources.py  
│   │       ├── reviews.py  
│   │       ├── dashboards.py  
│   │       └── jobs.py  
│   ├── models/  
│   │   ├── event.py  
│   │   ├── competitor.py  
│   │   ├── source.py  
│   │   ├── source_document.py  
│   │   ├── review.py  
│   │   └── scoring_rule.py  
│   ├── schemas/  
│   │   ├── event.py  
│   │   ├── competitor.py  
│   │   ├── source.py  
│   │   ├── review.py  
│   │   └── dashboard.py  
│   ├── repositories/  
│   │   ├── event_repo.py  
│   │   ├── competitor_repo.py  
│   │   ├── source_repo.py  
│   │   ├── review_repo.py  
│   │   └── dashboard_repo.py  
│   ├── services/  
│   │   ├── clinicaltrials_service.py  
│   │   ├── openrouter_service.py  
│   │   ├── extraction_service.py  
│   │   ├── normalization_service.py  
│   │   ├── scoring_service.py  
│   │   ├── dashboard_service.py  
│   │   └── review_service.py  
│   ├── jobs/  
│   │   ├── ingest_clinicaltrials.py  
│   │   ├── ingest_press_release.py  
│   │   └── recompute_scores.py  
│   └── utils/  
│       ├── hashing.py  
│       ├── dates.py  
│       └── text.py  
├── migrations/  
├── scripts/  
│   ├── seed_demo_data.py  
│   └── run_local_checks.py  
├── tests/  
│   ├── api/  
│   ├── services/  
│   └── repositories/  
├── docker/  
│   └── api.Dockerfile  
├── docker-compose.yml  
├── requirements.txt  
├── .env.example  
└── README.md  
```  
  
## Environment Variables  
  
Use the following environment variables:  
  
```env  
APP_ENV=dev  
SECRET_KEY=change-me  
DATABASE_URL=postgresql://...pooled...  
DATABASE_URL_DIRECT=postgresql://...direct...  
OPENROUTER_API_KEY=...  
OPENROUTER_MODEL_PRIMARY=google/gemini-2.0-flash-001  
OPENROUTER_MODEL_FALLBACK=anthropic/claude-3.5-sonnet  
CLINICALTRIALS_BASE_URL=https://clinicaltrials.gov/api/query/studies  
N8N_WEBHOOK_BASE_URL=  
```  
  
Use `DATABASE_URL` for the running app and `DATABASE_URL_DIRECT` for migrations.[cite:146][cite:152]  
  
## Database Schema  
  
Implement these core tables with Alembic migrations.  
  
### competitors  
- id UUID primary key  
- name string unique not null  
- parent_company string nullable  
- country string nullable  
- created_at timestamp default now  
  
### sources  
- id UUID primary key  
- source_name string not null  
- source_type string not null  
- source_tier string not null  
- base_url text nullable  
- active boolean default true  
- created_at timestamp default now  
  
### source_documents  
- id UUID primary key  
- source_id UUID foreign key  
- external_id string nullable  
- title text nullable  
- url text not null  
- published_at timestamp nullable  
- fetched_at timestamp default now  
- raw_text text nullable  
- raw_json jsonb nullable  
- content_hash string nullable  
- processing_status string default 'pending'  
  
### events  
- id UUID primary key  
- source_document_id UUID foreign key nullable  
- competitor_id UUID foreign key nullable  
- molecule_name string not null  
- reference_brand string not null  
- asset_code string nullable  
- event_type string not null  
- event_subtype string nullable  
- development_stage string nullable  
- indication string nullable  
- region string nullable  
- country string nullable  
- event_date timestamp nullable  
- summary text nullable  
- evidence_excerpt text nullable  
- confidence_score integer nullable  
- threat_score integer nullable  
- traffic_light string nullable  
- review_status string default 'pending'  
- created_at timestamp default now  
- updated_at timestamp default now  
  
### reviews  
- id UUID primary key  
- event_id UUID foreign key  
- reviewer_email string not null  
- action string not null  
- comment text nullable  
- created_at timestamp default now  
  
### scoring_rules  
- id UUID primary key  
- rule_name string not null  
- rule_group string not null  
- rule_config jsonb not null  
- active boolean default true  
- created_at timestamp default now  
  
## API Endpoints  
  
### Health  
- GET `/api/v1/health`  
  
### Events  
- GET `/api/v1/events`  
- POST `/api/v1/events`  
- GET `/api/v1/events/{event_id}`  
- PATCH `/api/v1/events/{event_id}`  
  
Supported filters:  
- competitor_name  
- molecule_name  
- event_type  
- traffic_light  
- review_status  
- region  
- country  
- date_from  
- date_to  
  
### Competitors  
- GET `/api/v1/competitors`  
- POST `/api/v1/competitors`  
- GET `/api/v1/competitors/{id}`  
  
### Sources  
- GET `/api/v1/sources`  
- POST `/api/v1/sources`  
- GET `/api/v1/source-documents`  
- GET `/api/v1/source-documents/{id}`  
  
### Reviews  
- GET `/api/v1/reviews`  
- POST `/api/v1/reviews`  
- POST `/api/v1/events/{event_id}/approve`  
- POST `/api/v1/events/{event_id}/reject`  
  
### Jobs  
- POST `/api/v1/jobs/ingest/clinicaltrials`  
- POST `/api/v1/jobs/ingest/press-release`  
- POST `/api/v1/jobs/recompute-scores`  
- GET `/api/v1/jobs/status`  
  
### Dashboard summary endpoints  
- GET `/api/v1/dashboards/summary`  
- GET `/api/v1/dashboards/top-threats`  
- GET `/api/v1/dashboards/recent-events`  
- GET `/api/v1/dashboards/review-queue`  
  
## ClinicalTrials.gov Integration  
  
Build `clinicaltrials_service.py` to:  
- query ClinicalTrials.gov API v2 for nivolumab biosimilar-relevant studies  
- accept configurable search terms  
- store raw response payload in `source_documents.raw_json`  
- create normalized event records  
- avoid duplicate inserts through content hash or external ID checks  
  
Initial search terms:  
- nivolumab biosimilar  
- ABP 206  
- HLX18  
  
ClinicalTrials.gov API v2 is the first source because it is structured and official.[cite:70][cite:79][cite:101]  
  
## OpenRouter Integration  
  
Build `openrouter_service.py` with a provider wrapper that can:  
- call the configured primary model  
- retry with fallback model  
- return strict JSON only  
  
Create one main extraction function:  
  
```python  
async def extract_competitive_event(text: str, source_url: str | None = None) -> dict:  
    ...  
```  
  
Return these fields:  
- competitor_name  
- asset_code  
- molecule_name  
- reference_brand  
- event_type  
- event_subtype  
- development_stage  
- indication  
- region  
- country  
- event_date  
- summary  
- evidence_excerpt  
- confidence_score  
  
Prompt rules:  
- return valid JSON only  
- unknown values must be null  
- do not invent dates  
- do not invent geography  
- keep summary under 40 words  
- include a confidence score from 0 to 100  
  
## Normalization Rules  
  
Build `normalization_service.py` to:  
- normalize molecule name to `nivolumab`  
- normalize brand to `Opdivo`  
- map competitor aliases to canonical names  
- normalize stage labels to one controlled vocabulary  
- normalize region and country labels  
  
Use a small alias dictionary in code for MVP.  
  
## Scoring Logic  
  
Build `scoring_service.py` with a simple additive model.  
  
Inputs:  
- event_type  
- development_stage  
- confidence_score  
- region or country relevance  
  
Output:  
- threat_score  
- traffic_light  
  
Default thresholds:  
- 0–34 Green  
- 35–64 Amber  
- 65–100 Red  
  
Suggested scoring behavior:  
- early clinical signal = low to medium  
- Phase 3 = medium to high  
- approval / launch / legal catalyst = high  
- low confidence lowers score  
  
Persist configurable defaults in `scoring_rules`.  
  
## Review Workflow  
  
Implement these statuses:  
- pending  
- approved  
- rejected  
  
Rules:  
- all ingested events default to `pending`  
- approved events appear in summary endpoints  
- rejected events remain stored with review log  
  
Review actions must:  
- store reviewer email  
- store action  
- store optional comment  
- preserve auditability  
  
## n8n Workflows  
  
### Workflow 1: Daily ingestion  
- Schedule trigger once daily  
- HTTP request to `POST /api/v1/jobs/ingest/clinicaltrials`  
- if success, log result  
- if failure, send notification  
  
### Workflow 2: Red event alert  
- schedule or webhook trigger  
- fetch approved Red events from last 24 hours  
- send digest email if any exist  
  
### Workflow 3: Weekly summary  
- weekly schedule  
- fetch approved events from last 7 days  
- summarize by competitor and traffic light  
- email summary  
  
Build these workflows after API endpoints are working. n8n documentation recommends starting with simple trigger-based workflows first.[cite:180][cite:183][cite:185]  
  
## Seed Data  
  
Seed at least these demo records:  
- Amgen / ABP 206 / Clinical Development / Phase 3 / Amber.[cite:16]  
- Henlius / HLX18 / Regulatory / IND / Amber.[cite:10][cite:34]  
- Zydus / launch-style India market event for demo narrative.[cite:35][cite:40]  
  
## Build Order  
  
Build strictly in this order:  
  
1. Create project structure.  
2. Implement config and DB connection.  
3. Implement SQLAlchemy models.  
4. Implement Alembic migrations.  
5. Implement health endpoint.  
6. Implement event CRUD and list filters.  
7. Implement source and review endpoints.  
8. Implement ClinicalTrials.gov ingestion.  
9. Implement raw payload storage.  
10. Implement normalization logic.  
11. Implement scoring logic.  
12. Implement OpenRouter extraction service.  
13. Implement one unstructured ingestion path.  
14. Implement review approval/rejection flow.  
15. Implement dashboard summary endpoints.  
16. Add seed script.  
17. Add Docker Compose and README.  
18. Add basic tests.  
19. Create n8n workflows.  
20. Run end-to-end demo test.  
  
## Coding Rules  
  
- Use Python type hints.  
- Use Pydantic schemas for all requests and responses.  
- Keep route handlers thin.  
- Put business logic in services.  
- Do not hardcode secrets.  
- Write simple and readable code.  
- Add at least one test for each core service.  
- Make code beginner-runnable from README.  
- Prefer explicit code over abstract frameworks.[cite:105][cite:111][cite:113]  
  
## Acceptance Tests  
  
The finished MVP must pass these checks:  
  
1. `docker compose up` starts app successfully.  
2. `/api/v1/health` returns success.  
3. One migration runs against Neon direct connection.  
4. One test event can be inserted and retrieved.  
5. ClinicalTrials.gov ingestion creates a source document and event.[cite:70][cite:79]  
6. OpenRouter extraction returns structured JSON.[cite:129][cite:162]  
7. Review endpoint can approve an event.  
8. Dashboard summary endpoint returns counts by traffic light.  
9. n8n can call ingestion endpoint successfully.[cite:180][cite:183]  
  
## Demo Flow  
  
The final demo must show:  
  
1. Trigger ClinicalTrials.gov ingestion.[cite:70][cite:79]  
2. Show stored event via API.  
3. Trigger one OpenRouter extraction from text.[cite:129][cite:162]  
4. Approve event through review endpoint.  
5. Show summary endpoint updated.  
6. Trigger or simulate n8n alert.[cite:180][cite:183]  
  
The full walkthrough must take less than 5 minutes.  

## Implementation Notes vs Original Plan

The current Biosi codebase matches the original end-to-end concept, with a few pragmatic adjustments:

1. Event metadata storage
   - Plan: all extracted fields (molecule_name, reference_brand, asset_code, event_subtype, evidence_excerpt, confidence_score, etc.) as first-class columns.
   - Implementation: key filter/sort fields (event_type, development_stage, indication, region, country, threat_score, traffic_light, review_status) are columns; additional extracted fields are stored in `events.metadata_json` (JSONB).
   - Rationale: keeps schema manageable while retaining full model output for audit and iteration.

2. Review model naming
   - Plan: `reviews` table with `reviewer_email`, `action`, `comment`.
   - Implementation: review records use `reviewer` and `review_notes`, and events expose `review_status` (`pending`/`approved`/`rejected`).
   - Rationale: naming aligned to FastAPI schemas; semantics are unchanged (email + action + optional comment + timestamp).

3. Runtime normalization for legacy values
   - Plan: assumes clean `review_status` and `traffic_light` values.
   - Implementation: dashboard services normalize malformed historical values (e.g., `"'pending'"`, `"red"`) into canonical forms (`"pending"`, `"Red"`) before serializing.
   - Rationale: protects response models from bad legacy data and prevents 500s in `/dashboards/recent-events`.

4. Press-release ingestion endpoint contract
   - Plan: `POST /api/v1/jobs/ingest/press-release` saves source text and a pending event.
   - Implementation: same endpoint with hardened schema:
     - Request: `{ "text": string (required, non-blank), "source_url": string|null (optional) }`.
     - Response: includes `source`, creation/update flags, and `extracted_event` with all model fields (many nullable).
   - Rationale: enforces Pydantic validation and produces a stable OpenAPI contract for n8n and tests.