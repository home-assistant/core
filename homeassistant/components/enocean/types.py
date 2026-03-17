"""Types for the EnOcean integration."""

from dataclasses import dataclass
import logging
from typing import Any, Final, TypedDict

from enocean_async import Gateway

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


type EnOceanPlatformStoreModel = dict[
    str, dict[str, Any]
]  # device_address: configuration


class EnOceanConfigStoreModel(TypedDict):
    """Represent EnOcean configuration store data."""

    entities: EnOceanPlatformStoreModel


class EnOceanConfigStore:
    """Manage EnOcean config store data."""

    STORAGE_VERSION: Final = 1
    STORAGE_KEY: Final = f"{DOMAIN}/config_store.json"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EnOceanConfigEntry,
    ) -> None:
        """Initialize config store."""
        self.hass = hass
        self.config_entry = config_entry
        self._store = Store[EnOceanConfigStoreModel](
            hass, self.STORAGE_VERSION, self.STORAGE_KEY
        )
        self.data = EnOceanConfigStoreModel(  # initialize with default structure
            entities={},
        )

    async def load_data(self) -> None:
        """Load config store data from storage."""
        if data := await self._store.async_load():
            self.data = EnOceanConfigStoreModel(**data)
            _LOGGER.debug(
                "Loaded EnOcean config data from storage, %s devices found",
                len(self.data["entities"]),
            )

    async def create_device(self, device_address: str, config: dict[str, Any]) -> None:
        """Create a device in the config store."""
        self.data["entities"][device_address] = config
        await self._store.async_save(self.data)


@dataclass(frozen=True)
class EnOceanConfigEntryData:
    """EnOcean data class."""

    gateway: Gateway
    config_store: EnOceanConfigStore


type EnOceanConfigEntry = ConfigEntry[EnOceanConfigEntryData]
