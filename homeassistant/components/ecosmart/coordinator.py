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


def retry_delay(err: EcosmartRateLimitError) -> int:
    """Return how many seconds to wait after the API rate limited a key.

    The server's Retry-After when it sends one; otherwise our own poll
    interval, rather than hammering a key that is already out of budget.
    """
    if err.retry_after is None:
        return int(SPOT_SCAN_INTERVAL.total_seconds())
    return err.retry_after


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
            # During the first refresh Home Assistant passes this delay on to
            # the config entry retry, so setup waits for it too.
            retry_after = retry_delay(err)
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
