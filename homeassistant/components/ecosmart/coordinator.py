"""Data update coordinator for the ecosmart integration."""

import asyncio
from typing import override

from aioecosmart import (
    EcosmartAuthError,
    EcosmartClient,
    EcosmartError,
    EcosmartRateLimitError,
    Identity,
    Spot,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SPOT_SCAN_INTERVAL

type EcosmartConfigEntry = ConfigEntry[EcosmartCoordinator]


class EcosmartCoordinator(DataUpdateCoordinator[dict[str, Spot]]):
    """Fetch the spot price for every grid exit point a key can reach.

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
        client: EcosmartClient,
        identity: Identity,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SPOT_SCAN_INTERVAL,
            always_update=False,
        )
        self.client = client
        self.identity = identity
        self.pocs = sorted({scope.poc for scope in identity.allowed_icps})

    @override
    async def _async_update_data(self) -> dict[str, Spot]:
        """Fetch every grid exit point at once."""
        try:
            results = await asyncio.gather(
                *(self.client.spot(poc) for poc in self.pocs)
            )
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
                retry_after = int(SPOT_SCAN_INTERVAL.total_seconds())
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
