"""Thin async wrapper around the Noonlight Dispatch API.

Only the handful of endpoints this integration needs are implemented:

* ``POST /dispatch/v1/alarms``                 — create an alarm (dispatch)
* ``GET  /dispatch/v1/alarms/{id}/status``     — poll an alarm's status
* ``POST /dispatch/v1/alarms/{id}/status``     — update/cancel an alarm

The wrapper is deliberately dumb: it builds URLs, signs requests with the
bearer token, raises typed errors, and returns parsed JSON. All policy
(state machine, dedupe, timers, audit) lives in the coordinator.
"""

import logging
from typing import Any

import httpx

from .const import (
    DEFAULT_TIMEOUT,
    ENV_CUSTOM,
    ENVIRONMENT_BASE_URLS,
    NON_PRODUCTION_ENVIRONMENTS,
    PATH_ALARM_STATUS,
    PATH_ALARMS,
)

_LOGGER = logging.getLogger(__name__)


def resolve_base_url(environment: str, custom_base_url: str | None) -> str:
    """Resolve a base URL from an environment label + optional override.

    For ``custom`` the override is required; for the named environments it is
    ignored. Any trailing slash is stripped so path concatenation is clean.
    """
    if environment == ENV_CUSTOM:
        if not custom_base_url:
            raise ValueError("custom environment requires a base URL")
        base = custom_base_url
    else:
        try:
            base = ENVIRONMENT_BASE_URLS[environment]
        except KeyError as err:
            raise ValueError(f"unknown environment: {environment}") from err
    return base.rstrip("/")


class NoonlightError(Exception):
    """Base error for all Noonlight API failures."""


class NoonlightAuthError(NoonlightError):
    """Raised when Noonlight rejects the bearer token (HTTP 401/403)."""


class NoonlightConnectionError(NoonlightError):
    """Raised when the Noonlight API is unreachable or times out."""


class NoonlightResponseError(NoonlightError):
    """Raised when Noonlight returns an unexpected status or body shape.

    ``status_code`` is the HTTP status when the error originated from one (None
    for body-shape errors on an otherwise-OK response). Callers such as the
    heartbeat use it to distinguish an expected 404 from a real 5xx/429 outage.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NoonlightApi:
    """Stateless async client for the Noonlight Dispatch API."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        token: str,
        *,
        base_url: str,
        environment: str,
    ) -> None:
        """Initialise the client.

        ``client`` is shared (provided by HA's ``get_async_client``); this
        wrapper never closes it. ``base_url`` is the already-resolved root for
        the chosen ``environment`` (see :func:`resolve_base_url`).
        """
        self._client = client
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._environment = environment

    @property
    def environment(self) -> str:
        """The configured environment label (production/sandbox/dev/custom)."""
        return self._environment

    @property
    def is_production(self) -> bool:
        """Whether this client can reach real responders.

        Custom endpoints are treated as production for safety: we cannot prove
        an arbitrary base URL is non-production.
        """
        return self._environment not in NON_PRODUCTION_ENVIRONMENTS

    @property
    def base_url(self) -> str:
        """Base URL for the configured environment."""
        return self._base_url

    # -- low-level ------------------------------------------------------------

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = await self._client.request(
                method,
                url,
                headers=self._headers,
                json=json,
                timeout=DEFAULT_TIMEOUT,
            )
        except (httpx.TimeoutException, httpx.TransportError) as err:
            raise NoonlightConnectionError(
                f"Could not reach Noonlight at {url}: {err}"
            ) from err

        if response.status_code in (401, 403):
            raise NoonlightAuthError(
                f"Noonlight rejected the token ({response.status_code})"
            )

        if response.status_code >= 400:
            raise NoonlightResponseError(
                f"Noonlight {method} {path} returned {response.status_code}: "
                f"{response.text[:500]}",
                status_code=response.status_code,
            )

        if not response.content:
            return {}

        try:
            data = response.json()
        except ValueError as err:
            raise NoonlightResponseError(
                f"Noonlight {method} {path} returned non-JSON body",
                status_code=response.status_code,
            ) from err

        if not isinstance(data, dict):
            raise NoonlightResponseError(
                f"Noonlight {method} {path} returned a non-object body",
                status_code=response.status_code,
            )
        return data

    # -- endpoints ------------------------------------------------------------

    async def create_alarm(
        self,
        *,
        services: list[str],
        name: str,
        phone: str,
        address: str,
        city: str,
        state: str,
        zip_code: str,
        instructions: str | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a Noonlight alarm and return the parsed response.

        ``services`` is a list of Noonlight service identifiers
        (``police``/``fire``/``medical``). ``instructions`` is optional
        free-text context for responders (e.g. which sensor triggered the
        dispatch). ``owner_id`` is an optional caller-defined identifier
        (used here to tag which property/site raised the alarm). The response
        is expected to contain at least an ``id`` and a ``status``.
        """
        payload = {
            "name": name,
            # Noonlight wants the number as digits *with* country code and
            # *without* a leading "+": "+12025550142" is rejected as an
            # unsupported format, but "12025550142" is accepted. We store the
            # canonical E.164 form on the entry and strip non-digits here.
            "phone": "".join(ch for ch in phone if ch.isdigit()),
            "services": dict.fromkeys(services, True),
            "location": {
                "address": {
                    "line1": address,
                    "city": city,
                    # Noonlight only accepts the uppercase 2-letter state code
                    # ("VA"); "va" and "Virginia" are both rejected.
                    "state": state.strip().upper(),
                    "zip": zip_code,
                }
            },
        }
        if instructions:
            # Noonlight requires an object with only the 'entry' key; a bare
            # string is rejected.
            payload["instructions"] = {"entry": instructions}
        if owner_id:
            payload["owner_id"] = owner_id
        data = await self._request("POST", PATH_ALARMS, json=payload)
        if "id" not in data:
            raise NoonlightResponseError("Create-alarm response had no 'id'")
        return data

    async def get_alarm_status(self, alarm_id: str) -> dict[str, Any]:
        """Fetch the current status of an alarm."""
        path = PATH_ALARM_STATUS.format(alarm_id=alarm_id)
        return await self._request("GET", path)

    async def cancel_alarm(self, alarm_id: str) -> dict[str, Any]:
        """Tell Noonlight to cancel an alarm.

        Noonlight ultimately decides whether responders are actually recalled;
        this only signals intent. Returns the parsed response body.
        """
        path = PATH_ALARM_STATUS.format(alarm_id=alarm_id)
        return await self._request("POST", path, json={"status": "CANCELED"})
