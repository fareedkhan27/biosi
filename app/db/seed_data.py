from decimal import Decimal

SOURCE_METADATA = [
    {
        "key": "clinicaltrials",
        "name": "ClinicalTrials.gov",
        "source_type": "regulatory",
        "base_url": "https://clinicaltrials.gov",
        "is_active": True,
    },
    {
        "key": "ema",
        "name": "European Medicines Agency",
        "source_type": "regulatory",
        "base_url": "https://www.ema.europa.eu",
        "is_active": True,
    },
    {
        "key": "fda",
        "name": "U.S. Food and Drug Administration",
        "source_type": "regulatory",
        "base_url": "https://www.fda.gov",
        "is_active": True,
    },
]

SCORING_RULES = [
    {
        "event_type": "trial_phase_change",
        "weight": Decimal("4.00"),
        "rationale": "Phase changes are high-signal competitive milestones.",
        "is_active": True,
    },
    {
        "event_type": "approval_or_rejection",
        "weight": Decimal("5.00"),
        "rationale": "Regulatory outcomes have immediate strategic impact.",
        "is_active": True,
    },
    {
        "event_type": "label_update",
        "weight": Decimal("3.00"),
        "rationale": "Label changes may affect market access and positioning.",
        "is_active": True,
    },
]
