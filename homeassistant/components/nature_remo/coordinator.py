"""Update coordinator for the Nature Remo integration."""

from dataclasses import dataclass
import logging
from typing import override

from aionatureremo import (
    Appliance,
    Device,
    NatureRemoAuthError,
    NatureRemoClient,
    NatureRemoError,
    NatureRemoRateLimitError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type NatureRemoConfigEntry = ConfigEntry[NatureRemoCoordinator]


@dataclass
class NatureRemoData:
    """Data fetched from the Nature API in one update cycle."""

    devices: dict[str, Device]
    appliances: dict[str, Appliance]


class NatureRemoCoordinator(DataUpdateCoordinator[NatureRemoData]):
    """Poll devices and appliances within the 30 req / 5 min rate budget."""

    config_entry: NatureRemoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NatureRemoConfigEntry,
        client: NatureRemoClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> NatureRemoData:
        """Fetch devices and appliances (two API calls, sequential)."""
        # Sequential rather than gather: deterministic error attribution and
        # no orphaned-task warnings when the first call fails.
        try:
            devices = await self.client.get_devices()
            appliances = await self.client.get_appliances()
        except NatureRemoAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except NatureRemoRateLimitError as err:
            if err.reset is not None:
                reset = dt_util.utc_from_timestamp(err.reset)
                delay = (reset - dt_util.utcnow()).total_seconds()
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_rate_limited",
                    translation_placeholders={
                        "reset": dt_util.as_local(reset).isoformat(timespec="seconds")
                    },
                    # Polling before the window resets only burns requests
                    # the API rejects. A reset already in the past carries
                    # no delay, so fall back to the normal interval.
                    retry_after=delay if delay > 0 else None,
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except NatureRemoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return NatureRemoData(
            devices={device.id: device for device in devices},
            appliances={appliance.id: appliance for appliance in appliances},
        )
