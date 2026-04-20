from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.biosimilar_competitor import BiosimilarCompetitor
from app.models.competitor import Competitor
from app.models.event import Event
from app.models.source import Source
from app.models.source_document import SourceDocument
from app.core.exceptions import ValidationError
from app.services.extraction_service import ExtractedEvent, extract_biosimilar_event_from_text
from app.services.scoring_service import calculate_threat_assessment


@dataclass(slots=True)
class PressReleaseIngestionResult:
    extracted_event: ExtractedEvent
    source_document_created: bool
    source_document_updated: bool
    event_created: bool
    event_updated: bool


# Explicit mapping from ExtractedEvent fields to Event model columns / metadata_json keys.
# Fields marked "column" are stored as first-class Event columns.
# Fields marked "metadata" are stored in Event.metadata_json.
# Fields marked "derived" are used to look up or create related rows.
#
# ExtractedEvent field       → Destination
# ─────────────────────────────────────────────────────────────────
# competitor_name            → derived  (Competitor row via _get_or_create_competitor)
# asset_code                 → metadata ("asset_code")
# molecule_name              → metadata ("molecule_name")
# reference_brand            → metadata ("reference_brand")
# event_type                 → column   Event.event_type
# event_subtype              → metadata ("event_subtype")
# development_stage          → metadata ("development_stage")  [used for scoring]
# indication                 → metadata ("indication")
# region                     → metadata ("region")             [used for scoring]
# country                    → metadata ("country")            [used for scoring]
# event_date                 → column   Event.event_date
# summary                    → column   Event.description
# evidence_excerpt           → metadata ("evidence_excerpt")
# confidence_score           → metadata ("confidence_score")   [used for scoring]


class PressReleaseIngestionService:
    SOURCE_KEY = "press_release"
    SOURCE_NAME = "Press Release"
    SOURCE_TYPE = "news"

    NON_COMPETITOR_NAME_TOKENS: tuple[str, ...] = (
        "university",
        "institute",
        "college",
        "hospital",
        "clinic",
        "center",
        "centre",
        "foundation",
        "agency",
        "ministry",
        "department",
        "government",
        "regulator",
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ingest_press_release(
        self,
        text: str,
        source_url: str | None,
    ) -> PressReleaseIngestionResult:
        if not text.strip():
            raise ValidationError("Press release text cannot be empty.")

        source = await self._get_or_create_source()
        extracted = await extract_biosimilar_event_from_text(text=text, source_url=source_url)
        normalized = self._normalize_extracted_event(extracted)

        if self._is_non_competitor_name(normalized.competitor_name):
            raise ValidationError("Extracted competitor is not a biosimilar developer.")

        competitor_profile = await self._resolve_competitor_profile(
            competitor_name=normalized.competitor_name,
            asset_code=normalized.asset_code,
        )

        competitor_name = (
            competitor_profile.name if competitor_profile is not None else normalized.competitor_name
        )
        if competitor_name is None:
            raise ValidationError("Press release must identify a biosimilar competitor.")

        competitor = await self._get_or_create_competitor(competitor_name)
        if competitor_profile is not None:
            competitor.company_type = "biosimilar_developer"

        source_document, source_document_created = await self._upsert_source_document(
            source=source,
            text=text,
            source_url=source_url,
            extracted_event=normalized,
        )
        _, event_created = await self._upsert_event(
            competitor=competitor,
            competitor_profile=competitor_profile,
            source_document=source_document,
            extracted_event=normalized,
        )

        await self.session.commit()

        return PressReleaseIngestionResult(
            extracted_event=normalized,
            source_document_created=source_document_created,
            source_document_updated=not source_document_created,
            event_created=event_created,
            event_updated=not event_created,
        )

    async def _get_or_create_source(self) -> Source:
        stmt = select(Source).where(Source.key == self.SOURCE_KEY)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        if source is not None:
            return source

        source = Source(
            key=self.SOURCE_KEY,
            name=self.SOURCE_NAME,
            source_type=self.SOURCE_TYPE,
            base_url=None,
            is_active=True,
        )
        self.session.add(source)
        await self.session.flush()
        return source

    async def _get_or_create_competitor(self, competitor_name: str) -> Competitor:
        stmt = select(Competitor).where(Competitor.name == competitor_name)
        result = await self.session.execute(stmt)
        competitor = result.scalar_one_or_none()
        if competitor is not None:
            return competitor

        competitor = Competitor(name=competitor_name, company_type="unknown", is_active=True)
        self.session.add(competitor)
        await self.session.flush()
        return competitor

    async def _upsert_source_document(
        self,
        source: Source,
        text: str,
        source_url: str | None,
        extracted_event: ExtractedEvent,
    ) -> tuple[SourceDocument, bool]:
        external_id = self._build_external_id(source_url=source_url, text=text)
        stmt = select(SourceDocument).where(
            SourceDocument.source_id == source.id,
            SourceDocument.external_id == external_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        title = self._build_document_title(extracted_event=extracted_event, text=text)
        url = source_url or f"urn:press-release:{external_id}"
        published_at = self._event_date_to_datetime(extracted_event.event_date)
        raw_payload = {
            "source_url": source_url,
            "text": text,
            "extracted_event": extracted_event.model_dump(mode="json"),
            "ingested_at": datetime.now(UTC).isoformat(),
        }

        if existing is None:
            doc = SourceDocument(
                source_id=source.id,
                external_id=external_id,
                title=title,
                url=url,
                published_at=published_at,
                raw_payload=raw_payload,
            )
            self.session.add(doc)
            await self.session.flush()
            return doc, True

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
        extracted_event: ExtractedEvent,
    ) -> tuple[Event, bool]:
        event_type = extracted_event.event_type or "press_release_update"
        stmt = select(Event).where(
            Event.competitor_id == competitor.id,
            Event.source_document_id == source_document.id,
            Event.event_type == event_type,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        title = self._build_event_title(extracted_event=extracted_event, source_document=source_document)
        description = extracted_event.summary
        event_date = self._event_date_to_date(extracted_event.event_date)
        metadata_json = {
            "event_subtype": extracted_event.event_subtype,
            "asset_code": extracted_event.asset_code,
            "molecule_name": extracted_event.molecule_name,
            "reference_brand": extracted_event.reference_brand,
            "development_stage": extracted_event.development_stage,
            "indication": extracted_event.indication,
            "region": extracted_event.region,
            "country": extracted_event.country,
            "competitor_tier": competitor_profile.tier if competitor_profile is not None else None,
            "competitor_geography": competitor_profile.geography if competitor_profile is not None else None,
            "estimated_launch_year": (
                competitor_profile.est_launch_year if competitor_profile is not None else None
            ),
            "evidence_excerpt": extracted_event.evidence_excerpt,
            "confidence_score": extracted_event.confidence_score,
        }

        assessment = calculate_threat_assessment(
            event_type=event_type,
            development_stage=extracted_event.development_stage,
            competitor_tier=competitor_profile.tier if competitor_profile is not None else None,
            confidence_score=extracted_event.confidence_score,
            region=extracted_event.region,
            country=extracted_event.country,
            indication=extracted_event.indication,
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
                event_type=event_type,
                title=title,
                description=description,
                event_date=event_date,
                indication=extracted_event.indication,
                metadata_json=metadata_json,
                threat_score=threat_score,
                traffic_light=traffic_light,
                review_status="pending",
            )
            self.session.add(event)
            await self.session.flush()
            return event, True

        existing.title = title
        existing.description = description
        existing.event_date = event_date
        existing.indication = extracted_event.indication
        existing.metadata_json = metadata_json
        existing.threat_score = threat_score
        existing.traffic_light = traffic_light
        await self.session.flush()
        return existing, False

    def _normalize_extracted_event(self, extracted_event: ExtractedEvent) -> ExtractedEvent:
        payload = extracted_event.model_dump(mode="json")

        payload["competitor_name"] = self._normalize_name(payload.get("competitor_name"))
        payload["asset_code"] = self._normalize_asset_code(payload.get("asset_code"))
        payload["molecule_name"] = self._normalize_name(payload.get("molecule_name"))
        payload["reference_brand"] = self._normalize_name(payload.get("reference_brand"))
        payload["event_type"] = self._normalize_token(payload.get("event_type"))
        payload["event_subtype"] = self._normalize_token(payload.get("event_subtype"))
        payload["development_stage"] = self._normalize_token(payload.get("development_stage"))
        payload["indication"] = self._normalize_name(payload.get("indication"))
        payload["region"] = self._normalize_name(payload.get("region"))
        payload["country"] = self._normalize_name(payload.get("country"))

        return ExtractedEvent.model_validate(payload)

    async def _resolve_competitor_profile(
        self,
        *,
        competitor_name: str | None,
        asset_code: str | None,
    ) -> BiosimilarCompetitor | None:
        result = await self.session.execute(select(BiosimilarCompetitor))
        profiles = list(result.scalars().all())

        normalized_name = self._normalize_lookup_name(competitor_name)
        normalized_asset_code = self._normalize_lookup_name(asset_code)
        for profile in profiles:
            if normalized_name and self._normalize_lookup_name(profile.name) == normalized_name:
                return profile
            if normalized_asset_code and self._normalize_lookup_name(profile.asset_name) == normalized_asset_code:
                return profile
        return None

    def _build_external_id(self, source_url: str | None, text: str) -> str:
        seed = source_url if source_url else text.strip()
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        return f"press-{digest}"

    def _build_document_title(self, extracted_event: ExtractedEvent, text: str) -> str:
        if extracted_event.summary:
            return extracted_event.summary[:180]
        first_line = text.strip().splitlines()[0] if text.strip() else "Press release"
        return first_line[:180]

    def _build_event_title(self, extracted_event: ExtractedEvent, source_document: SourceDocument) -> str:
        competitor = extracted_event.competitor_name or "Unknown Competitor"
        event_type = extracted_event.event_type or "press_release_update"
        return f"{competitor}: {event_type} ({source_document.external_id})"

    def _normalize_lookup_name(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().lower().replace("-", " ").replace("/", " ").split())
        return cleaned or None

    def _is_non_competitor_name(self, competitor_name: str | None) -> bool:
        normalized = self._normalize_lookup_name(competitor_name)
        if normalized is None:
            return False
        return any(token in normalized for token in self.NON_COMPETITOR_NAME_TOKENS)

    def _normalize_name(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        return " ".join(part.capitalize() for part in cleaned.split())

    def _normalize_asset_code(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            return None
        return cleaned.upper()

    def _normalize_token(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower().replace(" ", "_").replace("-", "_")
        if not cleaned:
            return None
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned

    def _event_date_to_date(self, value: str | None) -> date | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _event_date_to_datetime(self, value: str | None) -> datetime | None:
        parsed = self._event_date_to_date(value)
        if parsed is None:
            return None
        return datetime.combine(parsed, datetime.min.time(), tzinfo=UTC)
