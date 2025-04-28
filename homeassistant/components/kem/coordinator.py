"""The KEM coordinator."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from aiokem import AioKem, CommunicationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_MINUTES
from .data import HAAioKem

_LOGGER = logging.getLogger(__name__)

type KemConfigEntry = ConfigEntry[KemRuntimeData]


@dataclass
class KemRuntimeData:
    """Dataclass to hold runtime data for the KEM integration."""

    coordinators: dict[int, KemUpdateCoordinator]
    kem: HAAioKem
    homes: list[dict[str, Any]]


class KemUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching KEM data API."""

    config_entry: KemConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        config_entry: ConfigEntry,
        kem: AioKem,
        home_data: dict[str, Any],
        device_data: dict[str, Any],
        device_id: int,
        name: str,
    ) -> None:
        """Initialize."""
        self.kem = kem
        self.device_data = device_data
        self.device_id = device_id
        self.home_data = home_data
        super().__init__(
            hass=hass,
            logger=logger,
            config_entry=config_entry,
            name=name,
            update_interval=SCAN_INTERVAL_MINUTES,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        result = {}
        try:
            result = await self.kem.get_generator_data(self.device_id)
        except CommunicationError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from error
        return result

    @property
    def entry_unique_id(self) -> str:
        """Get the unique ID for the entry."""
        assert self.config_entry.unique_id
        return self.config_entry.unique_id
