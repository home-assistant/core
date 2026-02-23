"""Coordinator for Zinvolt."""

from datetime import timedelta
import logging

from zinvolt import ZinvoltClient
from zinvolt.exceptions import ZinvoltError
from zinvolt.models import BatteryState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type ZinvoltConfigEntry = ConfigEntry[dict[str, ZinvoltDeviceCoordinator]]


class ZinvoltDeviceCoordinator(DataUpdateCoordinator[BatteryState]):
    """Class for Zinvolt devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ZinvoltConfigEntry,
        client: ZinvoltClient,
        battery_id: str,
    ) -> None:
        """Initialize the Zinvolt device."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Zinvolt {battery_id}",
            update_interval=timedelta(minutes=5),
        )
        self._battery_id = battery_id
        self._client = client

    async def _async_update_data(self) -> BatteryState:
        """Update data from Zinvolt."""
        try:
            return await self._client.get_battery_status(self._battery_id)
        except ZinvoltError as err:
            raise UpdateFailed(
                translation_key="update_failed",
                translation_domain=DOMAIN,
            ) from err
