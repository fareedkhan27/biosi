"""Domain-level exception hierarchy for the Biosi platform.

Raise these from service / repository layers; catch them in FastAPI
exception handlers registered in `app/main.py`.
"""


class BiosiError(Exception):
    """Base exception for all Biosi domain errors."""


class NotFoundError(BiosiError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: object) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' not found.")


class ConflictError(BiosiError):
    """Raised when an operation would create a duplicate / conflict."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ValidationError(BiosiError):
    """Raised when business-rule validation fails (not Pydantic schema)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ExternalServiceError(BiosiError):
    """Raised when a downstream HTTP call or external service fails."""

    def __init__(self, service: str, detail: str) -> None:
        self.service = service
        super().__init__(f"External service '{service}' error: {detail}")
