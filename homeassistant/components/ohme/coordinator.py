"""Ohme coordinators."""

from abc import abstractmethod
from datetime import timedelta
import logging

from ohme import ApiException, OhmeApiClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OhmeBaseCoordinator(DataUpdateCoordinator[None]):
    """Base for all Ohme coordinators."""

    client: OhmeApiClient
    _default_update_interval: timedelta | None = timedelta(minutes=1)
    coordinator_name: str = ""

    def __init__(self, hass: HomeAssistant, client: OhmeApiClient) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="",
            update_interval=self._default_update_interval,
        )

        self.name = f"Ohme {self.coordinator_name}"
        self.client = client

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        try:
            await self._internal_update_data()
        except ApiException as e:
            raise UpdateFailed(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e

    @abstractmethod
    async def _internal_update_data(self) -> None:
        """Update coordinator data."""


class OhmeChargeSessionCoordinator(OhmeBaseCoordinator):
    """Coordinator to pull all updates from the API."""

    coordinator_name = "Charge Sessions"
    _default_update_interval = timedelta(seconds=30)

    async def _internal_update_data(self):
        """Fetch data from API endpoint."""
        await self.client.async_get_charge_session()


class OhmeAdvancedSettingsCoordinator(OhmeBaseCoordinator):
    """Coordinator to pull settings and charger state from the API."""

    coordinator_name = "Advanced Settings"

    async def _internal_update_data(self):
        """Fetch data from API endpoint."""
        await self.client.async_get_advanced_settings()
