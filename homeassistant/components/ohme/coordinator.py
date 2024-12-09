"""Ohme coordinators."""

from datetime import timedelta
import logging

from ohme import ApiException

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_INTERVAL_ADVANCED, DEFAULT_INTERVAL_CHARGESESSIONS

_LOGGER = logging.getLogger(__name__)


class OhmeChargeSessionsCoordinator(DataUpdateCoordinator):
    """Coordinator to pull main charge state and power/current draw."""

    def __init__(self, hass, config_entry):
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ohme Charge Sessions",
            update_interval=timedelta(
                minutes=config_entry.options.get(
                    "interval_chargesessions", DEFAULT_INTERVAL_CHARGESESSIONS
                )
            ),
        )
        self._client = config_entry.runtime_data.client

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            return await self._client.async_get_charge_sessions()

        except ApiException as e:
            raise UpdateFailed("Error communicating with API") from e


class OhmeAdvancedSettingsCoordinator(DataUpdateCoordinator):
    """Coordinator to pull CT clamp reading."""

    def __init__(self, hass, config_entry):
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ohme Advanced Settings",
            update_interval=timedelta(
                minutes=config_entry.options.get(
                    "interval_advanced", DEFAULT_INTERVAL_ADVANCED
                )
            ),
        )
        self._client = config_entry.runtime_data.client

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            return await self._client.async_get_advanced_settings()

        except ApiException as e:
            raise UpdateFailed("Error communicating with API") from e
