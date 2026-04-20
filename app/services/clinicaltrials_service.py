from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ExternalServiceError, ValidationError
from app.models.biosimilar_competitor import BiosimilarCompetitor
from app.models.competitor import Competitor
from app.models.event import Event
from app.models.source import Source
from app.models.source_document import SourceDocument
from app.services.scoring_service import calculate_threat_assessment


@dataclass(slots=True)
class ClinicalTrialsIngestionResult:
    search_terms: list[str]
    studies_seen: int = 0
    source_documents_created: int = 0
    source_documents_updated: int = 0
    events_created: int = 0
    events_updated: int = 0


class ClinicalTrialsIngestionService:
    """ClinicalTrials.gov API v2 ingestion service for Milestone 3."""

    SEARCH_TERMS: tuple[str, ...] = (
        "nivolumab biosimilar",
        "ABP 206",
        "HLX18",
    )

    EVENT_TYPE = "clinical_trial_update"
    DEFAULT_CONFIDENCE_SCORE = 70

    ACADEMIC_KEYWORDS: tuple[str, ...] = (
        "university",
        "institute",
        "college",
        "hospital",
        "clinic",
        "center",
        "centre",
        "foundation",
        "national cancer",
        "nci",
        "nih",
        "swog",
        "ecog",
        "nrg",
        "gog",
        "alliance",
        "cooperative",
        "consortium",
        "academic",
        "school of medicine",
        "mayo",
        "anderson",
        "memorial",
        "sloan",
    )

    KNOWN_COMPETITORS: tuple[str, ...] = (
        "amgen",
        "zydus",
        "sandoz",
        "xbrane",
        "intas",
        "accord",
        "boan",
        "henlius",
        "reliance life",
        "enzene",
        "dr. reddy",
        "biocon",
        "mabxience",
        "fresenius",
        "neuclone",
        "serum",
        "celltrion",
        "samsung bioepis",
        "innovent",
        "harbour biomed",
        "coherus",
        "pfizer",
        "mylan",
        "viatris",
    )

    KNOWN_COMPETITOR_ALIASES: dict[str, str] = {
        "amgen": "Amgen",
        "zydus": "Zydus Lifesciences",
        "zydus lifesciences": "Zydus Lifesciences",
        "sandoz": "Sandoz",
        "xbrane": "Xbrane / Intas",
        "intas": "Xbrane / Intas",
        "accord": "Accord",
        "boan": "Boan Biotech",
        "boan biotech": "Boan Biotech",
        "henlius": "Henlius",
        "shanghai henlius": "Henlius",
        "shanghai henlius biotec": "Henlius",
        "reliance life": "Reliance Life Sciences",
        "reliance life sciences": "Reliance Life Sciences",
        "enzene": "Enzene",
        "dr reddy": "Dr. Reddy's",
        "dr reddys": "Dr. Reddy's",
        "dr reddy s": "Dr. Reddy's",
        "biocon": "Biocon Biologics",
        "biocon biologics": "Biocon Biologics",
        "mabxience": "mAbxience",
        "fresenius": "Fresenius",
        "neuclone": "NeuClone",
        "serum": "Serum",
        "celltrion": "Celltrion",
        "samsung bioepis": "Samsung Bioepis",
        "innovent": "Innovent",
        "innovent biologics": "Innovent",
        "harbour biomed": "Harbour Biomed",
        "coherus": "Coherus",
        "pfizer": "Pfizer",
        "mylan": "Mylan",
        "viatris": "Viatris",
    }

    INDICATION_MAP: dict[str, str] = {
        "non-small cell lung": "NSCLC",
        "nsclc": "NSCLC",
        "lung cancer": "NSCLC",
        "melanoma": "Melanoma",
        "renal cell": "RCC",
        "kidney cancer": "RCC",
        "head and neck": "SCCHN",
        "squamous cell carcinoma of the head": "SCCHN",
        "esophageal": "ESCC/Esophageal",
        "gastric": "Gastric/GEJ",
        "colorectal": "MSI-H/dMMR CRC",
        "hepatocellular": "HCC",
        "urothelial": "Urothelial",
        "bladder": "Urothelial",
        "hodgkin": "cHL",
        "mesothelioma": "MPM",
    }

    COUNTRY_TO_REGION: dict[str, str] = {
        "united states": "North America",
        "canada": "North America",
        "germany": "Europe",
        "france": "Europe",
        "italy": "Europe",
        "spain": "Europe",
        "united kingdom": "Europe",
        "china": "Asia-Pacific",
        "japan": "Asia-Pacific",
        "south korea": "Asia-Pacific",
        "india": "Asia-Pacific",
        "australia": "Asia-Pacific",
        "brazil": "Latin America",
        "argentina": "Latin America",
    }

    def __init__(
        self,
        session: AsyncSession,
        base_url: str,
        search_terms: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")
        if "/api/v2/" not in self.base_url:
            raise ValidationError(
                "ClinicalTrials ingestion requires a ClinicalTrials.gov API v2 endpoint."
            )

        terms = search_terms if search_terms is not None else list(self.SEARCH_TERMS)
        normalized_terms = [term.strip() for term in terms if isinstance(term, str) and term.strip()]
        if not normalized_terms:
            raise ValidationError("At least one ClinicalTrials search term is required.")
        self.search_terms = normalized_terms

    async def ingest_default_terms(self) -> ClinicalTrialsIngestionResult:
        source = await self._get_source_or_raise()
        result = ClinicalTrialsIngestionResult(search_terms=list(self.search_terms))

        async with httpx.AsyncClient(timeout=30.0) as client:
            for term in self.search_terms:
                studies = await self._fetch_studies_for_term(client=client, term=term)

                for study in studies:
                    result.studies_seen += 1
                    document, was_created = await self._upsert_source_document(
                        source=source,
                        term=term,
                        study_payload=study,
                    )
                    if was_created:
                        result.source_documents_created += 1
                    else:
                        result.source_documents_updated += 1

                    normalized_fields = self._normalized_event_fields(study_payload=study, term=term)
                    if normalized_fields["competitor_name"] is None:
                        continue

                    competitor = await self._get_or_create_competitor(normalized_fields["competitor_name"])

                    competitor_profile = await self._get_competitor_profile(competitor)

                    event_created = await self._upsert_event(
                        competitor=competitor,
                        competitor_profile=competitor_profile,
                        source_document=document,
                        term=term,
                        study_payload=study,
                        normalized_fields=normalized_fields,
                    )
                    if event_created:
                        result.events_created += 1
                    else:
                        result.events_updated += 1

        await self.session.commit()
        return result

    async def _fetch_studies_for_term(self, client: httpx.AsyncClient, term: str) -> list[dict[str, Any]]:
        studies: list[dict[str, Any]] = []
        next_page_token: str | None = None

        while True:
            params: dict[str, str | int] = {
                "query.term": term,
                "pageSize": 100,
                "countTotal": "true",
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPStatusError as exc:
                detail = f"status={exc.response.status_code}"
                response_text = exc.response.text.strip()
                if response_text:
                    detail = f"{detail}, body={response_text[:300]}"
                raise ExternalServiceError("clinicaltrials.gov", detail) from exc
            except httpx.HTTPError as exc:
                raise ExternalServiceError("clinicaltrials.gov", str(exc)) from exc
            except ValueError as exc:
                raise ExternalServiceError("clinicaltrials.gov", "Invalid JSON response") from exc

            page_studies = payload.get("studies", [])
            if isinstance(page_studies, list):
                studies.extend([s for s in page_studies if isinstance(s, dict)])

            next_page_token = payload.get("nextPageToken")
            if not isinstance(next_page_token, str) or not next_page_token:
                break

        return studies

    async def _get_source_or_raise(self) -> Source:
        stmt = select(Source).where(Source.key == "clinicaltrials")
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        if source is None:
            raise ValidationError("Source 'clinicaltrials' is not seeded. Run `python -m app.db.seed`.")
        return source

    async def _upsert_source_document(
        self,
        source: Source,
        term: str,
        study_payload: dict[str, Any],
    ) -> tuple[SourceDocument, bool]:
        identification = self._as_dict(study_payload.get("protocolSection", {})).get(
            "identificationModule", {}
        )
        identification_module = self._as_dict(identification)

        nct_id = identification_module.get("nctId")
        external_id = nct_id if isinstance(nct_id, str) and nct_id else self._fallback_external_id(study_payload)

        stmt = select(SourceDocument).where(
            SourceDocument.source_id == source.id,
            SourceDocument.external_id == external_id,
        )
        db_result = await self.session.execute(stmt)
        existing = db_result.scalar_one_or_none()

        title = self._study_title(study_payload)
        url = self._study_url(external_id)
        published_at = self._study_published_at(study_payload)
        raw_payload = {
            "search_term": term,
            "study": study_payload,
            "ingested_at": datetime.now(UTC).isoformat(),
        }

        if existing is None:
            document = SourceDocument(
                source_id=source.id,
                external_id=external_id,
                title=title,
                url=url,
                published_at=published_at,
                raw_payload=raw_payload,
            )
            self.session.add(document)
            await self.session.flush()
            return document, True

        existing.title = title
        existing.url = url
        existing.published_at = published_at
        existing.raw_payload = raw_payload
        existing.retrieved_at = datetime.now(UTC)
        await self.session.flush()
        return existing, False

    async def _upsert_event(
        self,
        competitor: Competitor,
        competitor_profile: BiosimilarCompetitor | None,
        source_document: SourceDocument,
        term: str,
        study_payload: dict[str, Any],
        normalized_fields: dict[str, Any],
    ) -> bool:
        stmt = select(Event).where(
            Event.competitor_id == competitor.id,
            Event.source_document_id == source_document.id,
            Event.event_type == self.EVENT_TYPE,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        title = f"{source_document.external_id}: {self._study_title(study_payload)}"
        description = normalized_fields["summary"]
        event_date = normalized_fields["event_date"]
        metadata_json = self._study_metadata(study_payload=study_payload, term=term)
        metadata_json.update(
            {
                "source": "clinicaltrials.gov",
                "competitor_name": normalized_fields["competitor_name"],
                "molecule_name": normalized_fields["molecule_name"],
                "reference_brand": normalized_fields["reference_brand"],
                "asset_code": normalized_fields["asset_code"],
                "event_type": self.EVENT_TYPE,
                "development_stage": normalized_fields["development_stage"],
                "indication": normalized_fields["indication"],
                "region": normalized_fields["region"],
                "country": normalized_fields["country"],
                "competitor_tier": competitor_profile.tier if competitor_profile is not None else None,
                "competitor_geography": (
                    competitor_profile.geography if competitor_profile is not None else None
                ),
                "estimated_launch_year": (
                    competitor_profile.est_launch_year if competitor_profile is not None else None
                ),
                "event_date": normalized_fields["event_date"].isoformat()
                if normalized_fields["event_date"]
                else None,
                "evidence_excerpt": normalized_fields["evidence_excerpt"],
                "confidence_score": normalized_fields["confidence_score"],
            }
        )

        assessment = calculate_threat_assessment(
            event_type=self.EVENT_TYPE,
            development_stage=normalized_fields.get("development_stage"),
            competitor_tier=competitor_profile.tier if competitor_profile is not None else None,
            confidence_score=normalized_fields.get("confidence_score"),
            region=normalized_fields.get("region"),
            country=normalized_fields.get("country"),
            indication=normalized_fields.get("indication"),
            competitor_geography=competitor_profile.geography if competitor_profile is not None else None,
        )
        metadata_json["score_breakdown"] = assessment["score_breakdown"]
        metadata_json["missing_competitor_profile"] = competitor_profile is None
        threat_score = assessment["threat_score"]
        traffic_light = assessment["traffic_light"]

        if existing is None:
            event = Event(
                competitor_id=competitor.id,
                source_document_id=source_document.id,
                event_type=self.EVENT_TYPE,
                title=title,
                description=description,
                event_date=event_date,
                indication=normalized_fields["indication"],
                metadata_json=metadata_json,
                threat_score=threat_score,
                traffic_light=traffic_light,
                review_status="pending",
            )
            self.session.add(event)
            await self.session.flush()
            return True

        existing.title = title
        existing.description = description
        existing.event_date = event_date
        existing.indication = normalized_fields["indication"]
        existing.metadata_json = metadata_json
        existing.threat_score = threat_score
        existing.traffic_light = traffic_light
        await self.session.flush()
        return False

    def _normalized_event_fields(self, study_payload: dict[str, Any], term: str) -> dict[str, Any]:
        text_blob = self._study_text_blob(study_payload)
        asset_code = self._infer_asset_code(text_blob=text_blob, term=term)
        molecule_name = self._infer_molecule_name(text_blob=text_blob, term=term, asset_code=asset_code)
        reference_brand = self._infer_reference_brand(molecule_name=molecule_name)
        development_stage = self._infer_development_stage(study_payload)
        indication = self._infer_indication(study_payload)
        region, country = self._infer_region_country(study_payload)
        event_date = self._study_event_date(study_payload)
        evidence_excerpt = self._evidence_excerpt(study_payload)
        competitor_name = self._infer_competitor_name(study_payload)
        summary = self._study_description(study_payload)

        return {
            "competitor_name": competitor_name,
            "asset_code": asset_code,
            "molecule_name": molecule_name,
            "reference_brand": reference_brand,
            "development_stage": development_stage,
            "indication": indication,
            "region": region,
            "country": country,
            "event_date": event_date,
            "summary": summary,
            "evidence_excerpt": evidence_excerpt,
            "confidence_score": self.DEFAULT_CONFIDENCE_SCORE,
        }

    async def _get_or_create_competitor(self, inferred_name: str | None) -> Competitor:
        name = inferred_name or "Unknown Competitor"

        stmt = select(Competitor).where(Competitor.name == name)
        result = await self.session.execute(stmt)
        competitor = result.scalar_one_or_none()
        if competitor is not None:
            return competitor

        competitor = Competitor(name=name, company_type="program", is_active=True)
        self.session.add(competitor)
        await self.session.flush()
        return competitor

    async def _get_competitor_profile(
        self,
        competitor: Competitor,
    ) -> BiosimilarCompetitor | None:
        stmt = select(BiosimilarCompetitor).where(
            (BiosimilarCompetitor.competitor_id == competitor.id) | (BiosimilarCompetitor.name == competitor.name)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _study_title(self, study_payload: dict[str, Any]) -> str:
        identification_module = self._identification_module(study_payload)
        brief_title = identification_module.get("briefTitle")
        official_title = identification_module.get("officialTitle")
        if isinstance(brief_title, str) and brief_title:
            return brief_title
        if isinstance(official_title, str) and official_title:
            return official_title
        return "ClinicalTrials.gov Study"

    def _study_url(self, external_id: str) -> str:
        return f"https://clinicaltrials.gov/study/{external_id}"

    def _study_published_at(self, study_payload: dict[str, Any]) -> datetime | None:
        status_module = self._status_module(study_payload)
        published_value = self._as_dict(status_module.get("lastUpdatePostDateStruct", {})).get("date")
        return self._parse_datetime(published_value)

    def _study_event_date(self, study_payload: dict[str, Any]) -> date | None:
        status_module = self._status_module(study_payload)
        date_candidates = [
            self._as_dict(status_module.get("startDateStruct", {})).get("date"),
            self._as_dict(status_module.get("completionDateStruct", {})).get("date"),
            self._as_dict(status_module.get("lastUpdatePostDateStruct", {})).get("date"),
        ]
        for candidate in date_candidates:
            parsed = self._parse_date(candidate)
            if parsed is not None:
                return parsed
        return None

    def _study_description(self, study_payload: dict[str, Any]) -> str:
        status_module = self._status_module(study_payload)
        design_module = self._as_dict(self._protocol_section(study_payload).get("designModule", {}))
        description_module = self._as_dict(
            self._protocol_section(study_payload).get("descriptionModule", {})
        )
        overall_status = status_module.get("overallStatus")
        phases = design_module.get("phases")
        brief_summary = description_module.get("briefSummary")

        parts = ["ClinicalTrials.gov v2 ingestion"]
        if isinstance(overall_status, str) and overall_status:
            parts.append(f"status={overall_status}")
        if isinstance(phases, list) and phases:
            phase_text = ",".join([p for p in phases if isinstance(p, str)])
            if phase_text:
                parts.append(f"phase={phase_text}")
        if isinstance(brief_summary, str) and brief_summary.strip():
            parts.append(brief_summary.strip()[:250])

        return " | ".join(parts)

    def _study_metadata(self, study_payload: dict[str, Any], term: str) -> dict[str, Any]:
        status_module = self._status_module(study_payload)
        design_module = self._as_dict(self._protocol_section(study_payload).get("designModule", {}))
        sponsor_module = self._as_dict(self._protocol_section(study_payload).get("sponsorCollaboratorsModule", {}))
        conditions_module = self._as_dict(self._protocol_section(study_payload).get("conditionsModule", {}))

        metadata: dict[str, Any] = {
            "search_term": term,
            "nct_id": self._identification_module(study_payload).get("nctId"),
            "overall_status": status_module.get("overallStatus"),
            "phases": design_module.get("phases"),
            "lead_sponsor": self._as_dict(sponsor_module.get("leadSponsor", {})).get("name"),
            "conditions": conditions_module.get("conditions"),
        }
        return metadata

    def _study_text_blob(self, study_payload: dict[str, Any]) -> str:
        protocol_section = self._protocol_section(study_payload)
        description_module = self._as_dict(protocol_section.get("descriptionModule", {}))
        identification_module = self._identification_module(study_payload)
        conditions_module = self._as_dict(protocol_section.get("conditionsModule", {}))

        text_parts: list[str] = []
        for value in (
            identification_module.get("briefTitle"),
            identification_module.get("officialTitle"),
            description_module.get("briefSummary"),
            description_module.get("detailedDescription"),
        ):
            if isinstance(value, str) and value.strip():
                text_parts.append(value.strip())

        conditions = conditions_module.get("conditions")
        if isinstance(conditions, list):
            text_parts.extend([c for c in conditions if isinstance(c, str)])

        return " ".join(text_parts)

    def _infer_asset_code(self, text_blob: str, term: str) -> str | None:
        lookup = f"{text_blob} {term}".upper()
        if "ABP 206" in lookup:
            return "ABP 206"
        if "HLX18" in lookup:
            return "HLX18"
        return None

    def _infer_molecule_name(self, text_blob: str, term: str, asset_code: str | None) -> str | None:
        lookup = f"{text_blob} {term}".lower()
        if "nivolumab" in lookup:
            return "nivolumab"
        if "biosimilar" in lookup and asset_code in {"ABP 206", "HLX18"}:
            return "nivolumab"
        if "nivolumab biosimilar" in term.lower():
            return "nivolumab"
        return None

    def _infer_reference_brand(self, molecule_name: str | None) -> str | None:
        if molecule_name == "nivolumab":
            return "Opdivo"
        return None

    def _infer_development_stage(self, study_payload: dict[str, Any]) -> str | None:
        design_module = self._as_dict(self._protocol_section(study_payload).get("designModule", {}))
        phases = design_module.get("phases")
        if not isinstance(phases, list):
            return None

        phase_text = ", ".join([phase for phase in phases if isinstance(phase, str)]).strip()
        if not phase_text:
            return None

        # Normalize to space-separated uppercase for matching (API returns e.g. "PHASE3", "EARLY_PHASE1")
        normalized = phase_text.replace("_", " ").upper()
        if "PHASE4" in normalized or "PHASE 4" in normalized:
            return "Phase 4"
        if "PHASE3" in normalized or "PHASE 3" in normalized:
            return "Phase 3"
        if "PHASE2" in normalized or "PHASE 2" in normalized:
            return "Phase 2"
        if "PHASE1" in normalized or "PHASE 1" in normalized:
            return "Phase 1"
        return None

    def _infer_indication(self, study_payload: dict[str, Any]) -> str | None:
        conditions = self._study_conditions(study_payload)
        if not conditions:
            return "Other/Extrapolation"

        first_condition = next((condition for condition in conditions if condition.strip()), "")
        search_spaces = [first_condition.lower(), " ".join(conditions).lower()]
        for search_space in search_spaces:
            for fragment, bucket in self.INDICATION_MAP.items():
                if fragment in search_space:
                    return bucket
        return "Other/Extrapolation"

    def _infer_region_country(self, study_payload: dict[str, Any]) -> tuple[str | None, str | None]:
        contacts_locations_module = self._as_dict(
            self._protocol_section(study_payload).get("contactsLocationsModule", {})
        )
        locations = contacts_locations_module.get("locations")
        if not isinstance(locations, list) or not locations:
            return None, None

        countries = {
            location.get("country")
            for location in locations
            if isinstance(location, dict) and isinstance(location.get("country"), str)
        }
        normalized_countries = {country.strip() for country in countries if country and country.strip()}
        if not normalized_countries:
            return None, None

        if len(normalized_countries) == 1:
            country = next(iter(normalized_countries))
            region = self.COUNTRY_TO_REGION.get(country.lower())
            return region, country

        return "Global", None

    def _infer_competitor_name(self, study_payload: dict[str, Any]) -> str | None:
        sponsor_module = self._as_dict(
            self._protocol_section(study_payload).get("sponsorCollaboratorsModule", {})
        )

        lead_sponsor = self._as_dict(sponsor_module.get("leadSponsor", {})).get("name")

        if isinstance(lead_sponsor, str) and lead_sponsor.strip():
            normalized = self._normalize_organization_name(lead_sponsor)
            matched = self._match_known_competitor(normalized)
            if matched is not None:
                return matched

        collaborators = sponsor_module.get("collaborators", [])
        if isinstance(collaborators, list):
            for collab in collaborators:
                collab_name = self._as_dict(collab).get("name")
                if not isinstance(collab_name, str) or not collab_name.strip():
                    continue
                normalized_c = self._normalize_organization_name(collab_name)
                matched_c = self._match_known_competitor(normalized_c)
                if matched_c is not None:
                    return matched_c

        return None

    def _normalize_organization_name(self, name: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", " ", name.lower())
        return " ".join(cleaned.split())

    def _match_known_competitor(self, normalized_name: str) -> str | None:
        if normalized_name in self.KNOWN_COMPETITOR_ALIASES:
            return self.KNOWN_COMPETITOR_ALIASES[normalized_name]

        for keyword in sorted(self.KNOWN_COMPETITORS, key=len, reverse=True):
            normalized_keyword = self._normalize_organization_name(keyword)
            if normalized_keyword in normalized_name:
                return self.KNOWN_COMPETITOR_ALIASES.get(normalized_keyword, keyword.title())
        return None

    def _matches_keywords(self, normalized_name: str, keywords: tuple[str, ...]) -> bool:
        return any(self._normalize_organization_name(keyword) in normalized_name for keyword in keywords)

    def _study_conditions(self, study_payload: dict[str, Any]) -> list[str]:
        conditions_module = self._as_dict(self._protocol_section(study_payload).get("conditionsModule", {}))
        conditions = conditions_module.get("conditions")
        if not isinstance(conditions, list):
            return []
        return [condition.strip() for condition in conditions if isinstance(condition, str) and condition.strip()]

    def _evidence_excerpt(self, study_payload: dict[str, Any]) -> str | None:
        description_module = self._as_dict(
            self._protocol_section(study_payload).get("descriptionModule", {})
        )
        for key in ("briefSummary", "detailedDescription"):
            value = description_module.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:300]
        return None

    def _fallback_external_id(self, study_payload: dict[str, Any]) -> str:
        title = self._study_title(study_payload)
        digest = hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]
        return f"unknown-{digest}"

    def _protocol_section(self, study_payload: dict[str, Any]) -> dict[str, Any]:
        return self._as_dict(study_payload.get("protocolSection", {}))

    def _identification_module(self, study_payload: dict[str, Any]) -> dict[str, Any]:
        return self._as_dict(self._protocol_section(study_payload).get("identificationModule", {}))

    def _status_module(self, study_payload: dict[str, Any]) -> dict[str, Any]:
        return self._as_dict(self._protocol_section(study_payload).get("statusModule", {}))

    def _parse_datetime(self, value: Any) -> datetime | None:
        parsed_date = self._parse_date(value)
        if parsed_date is None:
            return None
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)

    def _parse_date(self, value: Any) -> date | None:
        if not isinstance(value, str) or not value:
            return None

        candidates = [value, value[:10], f"{value}-01", f"{value}-01-01"]
        for candidate in candidates:
            try:
                return datetime.strptime(candidate, "%Y-%m-%d").date()
            except ValueError:
                continue
        return None

    def _as_dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}
