"""Ohme coordinators."""

from datetime import timedelta
import logging

from ohme import ApiException, OhmeApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type OhmeConfigEntry = ConfigEntry[list[DataUpdateCoordinator]]


class OhmeChargeSessionCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to pull all updates from the API."""

    config_entry: OhmeConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: OhmeConfigEntry, client: OhmeApiClient
    ) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ohme Charge Session Coordinator",
            update_interval=timedelta(seconds=30),
            config_entry=entry,
        )

        self.client = client

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        try:
            await self.client.async_get_charge_session()
        except ApiException as e:
            raise UpdateFailed(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e


class OhmeAdvancedSettingsCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to pull settings and charger state from the API."""

    config_entry: OhmeConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: OhmeConfigEntry, client: OhmeApiClient
    ) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ohme Advanced Settings Coordinator",
            update_interval=timedelta(minutes=1),
            config_entry=entry,
        )

        self.client = client

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        try:
            await self.client.async_get_advanced_settings()
        except ApiException as e:
            raise UpdateFailed(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e
