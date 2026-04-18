from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def _normalize_postgres_scheme(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


# asyncpg does not understand libpq-style params (sslmode, channel_binding, etc.)
# Convert them to the asyncpg equivalents.
_ASYNCPG_UNSUPPORTED_PARAMS = {"sslmode", "channel_binding", "options"}
_SSLMODE_TO_ASYNCPG = {
    "require": "require",
    "verify-ca": "verify_ca",
    "verify-full": "verify_full",
    "disable": "disable",
    "prefer": "prefer",
    "allow": "allow",
}


def _adapt_query_for_asyncpg(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    ssl_value = None
    sslmode = params.pop("sslmode", [None])[0]
    if sslmode:
        ssl_value = _SSLMODE_TO_ASYNCPG.get(sslmode, "require")

    # Drop params that asyncpg doesn't understand
    for key in list(params.keys()):
        if key in _ASYNCPG_UNSUPPORTED_PARAMS:
            params.pop(key)

    if ssl_value:
        params["ssl"] = [ssl_value]

    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


def to_async_database_url(url: str) -> str:
    normalized = _normalize_postgres_scheme(url)

    if normalized.startswith("postgresql+asyncpg://"):
        return _adapt_query_for_asyncpg(normalized)

    if normalized.startswith("postgresql+psycopg://"):
        base = normalized.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        return _adapt_query_for_asyncpg(base)

    if normalized.startswith("postgresql://"):
        base = normalized.replace("postgresql://", "postgresql+asyncpg://", 1)
        return _adapt_query_for_asyncpg(base)

    return normalized


def to_sync_database_url(url: str) -> str:
    normalized = _normalize_postgres_scheme(url)

    if normalized.startswith("postgresql+psycopg://"):
        return normalized

    if normalized.startswith("postgresql+asyncpg://"):
        return normalized.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+psycopg://", 1)

    return normalized
