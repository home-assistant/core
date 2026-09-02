"""Data update coordinators for the ecosmart integration."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import override

from aioecosmart import (
    EcosmartAuthError,
    EcosmartClient,
    EcosmartError,
    EcosmartRateLimitError,
    Forecast,
    Identity,
    Spot,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type EcosmartConfigEntry = ConfigEntry[EcosmartRuntimeData]


class EcosmartCoordinator[_DataT](DataUpdateCoordinator[dict[str, _DataT]]):
    """Fetch one kind of price for every grid exit point a key can reach.

    Prices are published per grid exit point -- the POC, the substation where
    the local network draws off the national grid -- and not per connection
    point, so several ICPs behind the same one share a single request. The
    result is keyed by POC and then serves every entity that needs it.
    """

    config_entry: EcosmartConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EcosmartConfigEntry,
        pocs: list[str],
        *,
        name: str,
        update_interval: timedelta,
        fetch: Callable[[str], Awaitable[_DataT]],
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} {name}",
            update_interval=update_interval,
            always_update=False,
        )
        self.pocs = pocs
        self._fetch = fetch
        self._interval_seconds = int(update_interval.total_seconds())

    @override
    async def _async_update_data(self) -> dict[str, _DataT]:
        """Fetch every grid exit point at once."""
        try:
            results = await asyncio.gather(*(self._fetch(poc) for poc in self.pocs))
        except EcosmartAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except EcosmartRateLimitError as err:
            # First refresh converts UpdateFailed to ConfigEntryNotReady and
            # ignores retry_after (~5s HA retry). Do not claim a delay then.
            if self.data is None:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="rate_limited_setup",
                ) from err
            retry_after = err.retry_after
            if retry_after is None:
                # No Retry-After header: fall back to our own cadence rather
                # than hammering a key that is already out of budget.
                retry_after = self._interval_seconds
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                translation_placeholders={"retry_after": str(retry_after)},
                retry_after=retry_after,
            ) from err
        except EcosmartError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        return dict(zip(self.pocs, results, strict=True))


@dataclass(kw_only=True, frozen=True)
class EcosmartRuntimeData:
    """Everything a loaded ecosmart config entry owns."""

    client: EcosmartClient
    identity: Identity
    spot_coordinator: EcosmartCoordinator[Spot]
    forecast_coordinator: EcosmartCoordinator[Forecast]
