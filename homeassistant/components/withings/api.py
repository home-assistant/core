"""Api for Withings."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import arrow
import requests
from withings_api import AbstractWithingsApi, DateType
from withings_api.common import (
    GetSleepSummaryField,
    MeasureGetMeasGroupCategory,
    MeasureGetMeasResponse,
    MeasureType,
    NotifyAppli,
    NotifyListResponse,
    SleepGetSummaryResponse,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    OAuth2Session,
)

from .const import LOGGER

_RETRY_COEFFICIENT = 0.5


class ConfigEntryWithingsApi(AbstractWithingsApi):
    """Withing API that uses HA resources."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        implementation: AbstractOAuth2Implementation,
    ) -> None:
        """Initialize object."""
        self._hass = hass
        self.config_entry = config_entry
        self._implementation = implementation
        self.session = OAuth2Session(hass, config_entry, implementation)

    def _request(
        self, path: str, params: dict[str, Any], method: str = "GET"
    ) -> dict[str, Any]:
        """Perform an async request."""
        asyncio.run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self._hass.loop
        ).result()

        access_token = self.config_entry.data["token"]["access_token"]
        response = requests.request(
            method,
            f"{self.URL}/{path}",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        return response.json()

    async def _do_retry(self, func: Callable[[], Awaitable[Any]], attempts=3) -> Any:
        """Retry a function call.

        Withings' API occasionally and incorrectly throws errors.
        Retrying the call tends to work.
        """
        exception = None
        for attempt in range(1, attempts + 1):
            LOGGER.debug("Attempt %s of %s", attempt, attempts)
            try:
                return await func()
            except Exception as exception1:  # pylint: disable=broad-except
                LOGGER.debug(
                    "Failed attempt %s of %s (%s)", attempt, attempts, exception1
                )
                # Make each backoff pause a little bit longer
                await asyncio.sleep(_RETRY_COEFFICIENT * attempt)
                exception = exception1
                continue

        if exception:
            raise exception

    async def async_measure_get_meas(
        self,
        meastype: MeasureType | None = None,
        category: MeasureGetMeasGroupCategory | None = None,
        startdate: DateType | None = arrow.utcnow(),
        enddate: DateType | None = arrow.utcnow(),
        offset: int | None = None,
        lastupdate: DateType | None = arrow.utcnow(),
    ) -> MeasureGetMeasResponse:
        """Get measurements."""

        async def call_super() -> MeasureGetMeasResponse:
            return await self._hass.async_add_executor_job(
                self.measure_get_meas,
                meastype,
                category,
                startdate,
                enddate,
                offset,
                lastupdate,
            )

        return await self._do_retry(call_super)

    async def async_sleep_get_summary(
        self,
        data_fields: Iterable[GetSleepSummaryField],
        startdateymd: DateType | None = arrow.utcnow(),
        enddateymd: DateType | None = arrow.utcnow(),
        offset: int | None = None,
        lastupdate: DateType | None = arrow.utcnow(),
    ) -> SleepGetSummaryResponse:
        """Get sleep data."""

        async def call_super() -> SleepGetSummaryResponse:
            return await self._hass.async_add_executor_job(
                self.sleep_get_summary,
                data_fields,
                startdateymd,
                enddateymd,
                offset,
                lastupdate,
            )

        return await self._do_retry(call_super)

    async def async_notify_list(
        self, appli: NotifyAppli | None = None
    ) -> NotifyListResponse:
        """List webhooks."""

        async def call_super() -> NotifyListResponse:
            return await self._hass.async_add_executor_job(self.notify_list, appli)

        return await self._do_retry(call_super)

    async def async_notify_subscribe(
        self,
        callbackurl: str,
        appli: NotifyAppli | None = None,
        comment: str | None = None,
    ) -> None:
        """Subscribe to webhook."""

        async def call_super() -> None:
            await self._hass.async_add_executor_job(
                self.notify_subscribe, callbackurl, appli, comment
            )

        await self._do_retry(call_super)

    async def async_notify_revoke(
        self, callbackurl: str | None = None, appli: NotifyAppli | None = None
    ) -> None:
        """Revoke webhook."""

        async def call_super() -> None:
            await self._hass.async_add_executor_job(
                self.notify_revoke, callbackurl, appli
            )

        await self._do_retry(call_super)
