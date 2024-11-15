"""Coordinator for the Aussie Broadband integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, TypedDict

from aussiebb.asyncio import AussieBB
from aussiebb.exceptions import UnrecognisedServiceType

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AussieBroadbandServiceData(TypedDict, total=False):
    """Aussie Broadband service information, extended with the coordinator."""

    coordinator: AussieBroadbandDataUpdateCoordinator
    description: str
    name: str
    service_id: str
    type: str


type AussieBroadbandConfigEntry = ConfigEntry[list[AussieBroadbandServiceData]]


class AussieBroadbandDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Aussie Broadand data update coordinator."""

    def __init__(self, hass: HomeAssistant, client: AussieBB, service_id: str) -> None:
        """Initialize Atag coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Aussie Broadband {service_id}",
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
        )
        self._client = client
        self._service_id = service_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            return await self._client.get_usage(self._service_id)
        except UnrecognisedServiceType as err:
            raise UpdateFailed(f"Service {self._service_id} was unrecognised") from err
