"""Coordinator for MELCloud Home."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging

from aiomelcloudhome import ATAUnit, ATWUnit, MELCloudHome, UserContext
from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)


type MelCloudHomeConfigEntry = ConfigEntry[MelCloudHomeData]


@dataclass(frozen=True, kw_only=True)
class MelCloudHomeData:
    """Runtime data stored in the config entry."""

    coordinator: MelCloudHomeCoordinator


class MelCloudHomeCoordinator(DataUpdateCoordinator[UserContext]):
    """Coordinator to manage fetching MELCloud Home data."""

    config_entry: MelCloudHomeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MelCloudHomeConfigEntry,
        client: MELCloudHome,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.known_ata: set[str] = set()
        self.known_atw: set[str] = set()
        self.new_ata_callbacks: list[Callable[[list[ATAUnit]], None]] = []
        self.new_atw_callbacks: list[Callable[[list[ATWUnit]], None]] = []

    def _notify_new_units(self, data: UserContext) -> None:
        """Notify callbacks when new units are discovered."""
        current_ata = [
            unit for building in data.buildings for unit in building.air_to_air_units
        ]
        current_ata_ids = {unit.id for unit in current_ata}
        self.known_ata &= current_ata_ids
        new_ata_ids = current_ata_ids - self.known_ata
        new_ata_units = [unit for unit in current_ata if unit.id in new_ata_ids]
        if new_ata_units:
            _LOGGER.debug("Discovered new ATA units: %s", new_ata_units)
            self.known_ata.update(unit.id for unit in new_ata_units)
            for ata_callback in self.new_ata_callbacks:
                ata_callback(new_ata_units)

        current_atw_units = [
            unit for building in data.buildings for unit in building.air_to_water_units
        ]
        current_atw_ids = {unit.id for unit in current_atw_units}
        self.known_atw &= current_atw_ids
        new_atw_ids = current_atw_ids - self.known_atw
        new_atw_units = [unit for unit in current_atw_units if unit.id in new_atw_ids]
        if new_atw_units:
            _LOGGER.debug("Discovered new ATW units: %s", new_atw_units)
            self.known_atw.update(unit.id for unit in new_atw_units)
            for atw_callback in self.new_atw_callbacks:
                atw_callback(new_atw_units)

    async def _async_update_data(self) -> UserContext:
        """Fetch data from the MELCloud Home API."""
        try:
            data = await self.client.get_context()
        except MelCloudHomeAuthenticationError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except MelCloudHomeConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except MelCloudHomeTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        else:
            self._notify_new_units(data)
            return data
