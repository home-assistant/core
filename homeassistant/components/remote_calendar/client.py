"""Specifies the parameter for the httpx download."""

import logging
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient, Auth, BasicAuth, Response, Timeout

_LOGGER = logging.getLogger(__name__)


async def get_calendar(
    client: AsyncClient,
    url: str,
    username: str | None = None,
    password: str | None = None,
) -> Response:
    """Make an HTTP GET request using Home Assistant's async HTTPX client with timeout."""
    headers: dict[str, str] = {}
    auth: Auth | None = None

    # Set up HTTP Basic Auth if credentials provided
    if username and password:
        auth = BasicAuth(username, password)
        _LOGGER.debug("HTTP Basic Auth enabled for username: %s", username)

    # Extract API key from URL query parameters and add as header
    # Some services (like Radarr) prefer header-based authentication
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    # Check for common API key parameter names
    for param_name in ("apikey", "api_key", "api-key", "key"):
        if param_name in query_params:
            api_key = query_params[param_name][0]
            # Use X-Api-Key header (standard for Radarr/Sonarr)
            headers["X-Api-Key"] = api_key
            _LOGGER.debug(
                "Found API key parameter '%s' in URL, adding as X-Api-Key header",
                param_name,
            )
            break

    # Log request details for debugging
    _LOGGER.debug("Making calendar request to: %s", url)
    if headers:
        _LOGGER.debug(
            "Request headers: %s",
            {k: "***" if "key" in k.lower() else v for k, v in headers.items()},
        )
    else:
        _LOGGER.debug("No additional headers being sent")

    response = await client.get(
        url,
        headers=headers,
        auth=auth,
        follow_redirects=True,
        timeout=Timeout(5, read=30, write=5, pool=5),
    )

    # Log response details
    _LOGGER.debug(
        "Response status: %s %s",
        response.status_code,
        response.reason_phrase if hasattr(response, "reason_phrase") else "",
    )
    _LOGGER.debug("Response headers: %s", dict(response.headers))

    # Log response body snippet for errors (first 500 chars)
    if response.status_code >= 400:
        body_preview = response.text[:500] if response.text else "(empty response)"
        _LOGGER.debug("Response body preview: %s", body_preview)

    return response
