"""The Rituals Perfume Genie data update coordinator."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from ritualsgenie import (
    RitualsGenie,
    RitualsGenieAuthenticationError,
    RitualsGenieError,
    RitualsGenieHub,
    RitualsGenieRateLimitError,
    RitualsGenieSensors,
    Sensor,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Only the sensors the entities use; every sensor is a request of its own.
SENSORS = (Sensor.BATTERY, Sensor.FILL, Sensor.PERFUME, Sensor.WIFI)

type RitualsConfigEntry = ConfigEntry[dict[str, RitualsDataUpdateCoordinator]]


@dataclass
class RitualsData:
    """State and sensor readings of a diffuser."""

    hub: RitualsGenieHub
    sensors: RitualsGenieSensors


class RitualsDataUpdateCoordinator(DataUpdateCoordinator[RitualsData]):
    """Manage fetching Rituals Perfume Genie device data."""

    config_entry: RitualsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RitualsConfigEntry,
        client: RitualsGenie,
        hub: RitualsGenieHub,
        update_interval: timedelta,
    ) -> None:
        """Initialize global Rituals Perfume Genie data updater."""
        self.client = client
        self.hub_hash = hub.hash
        self.hublot = hub.hublot
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{hub.hublot}",
            update_interval=update_interval,
        )

    @override
    async def _async_update_data(self) -> RitualsData:
        """Fetch data from Rituals."""
        try:
            hub = await self.client.hub(self.hub_hash)
            sensors = await self.client.sensors(hub, only=SENSORS)
        except RitualsGenieAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except RitualsGenieRateLimitError as err:
            raise UpdateFailed(str(err), retry_after=err.retry_after) from err
        except RitualsGenieError as err:
            raise UpdateFailed(str(err)) from err

        return RitualsData(hub=hub, sensors=sensors)
