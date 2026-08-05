"""Coordinator for MELCloud Home."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import override

from aiomelcloudhome import ATAUnit, ATWUnit, MELCloudHome, UserContext
from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)


type MelCloudHomeConfigEntry = ConfigEntry[MelCloudHomeCoordinator]


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
        self.ata_units: dict[str, ATAUnit] = {}
        self.atw_units: dict[str, ATWUnit] = {}
        self.ata_energy: dict[str, float | None] = {}
        self.atw_energy: dict[str, float | None] = {}
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

        self._async_remove_stale_devices(current_ata_ids | current_atw_ids)

    @callback
    def _async_remove_stale_devices(self, current_ids: set[str]) -> None:
        """Remove devices for units that are no longer in the account."""
        registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        ):
            if not any(
                identifier[0] == DOMAIN and identifier[1] in current_ids
                for identifier in device.identifiers
            ):
                _LOGGER.debug("Removing stale device: %s", device.identifiers)
                registry.async_remove_device(device.id)

    @override
    async def _async_update_data(self) -> UserContext:
        """Fetch data from the MELCloud Home API."""
        try:
            data = await self.client.get_context()

            start_of_month = utcnow().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            for building in data.buildings:
                for ata_unit in building.air_to_air_units:
                    self.ata_units[ata_unit.id] = ata_unit
                    if (
                        ata_unit.capabilities
                        and ata_unit.capabilities.has_energy_consumed_meter
                    ):
                        energy = await self.client.get_energy_telemetry(
                            ata_unit.id,
                            from_dt=start_of_month,
                            to_dt=utcnow(),
                        )
                        self.ata_energy[ata_unit.id] = sum(
                            float(e.value) for e in energy
                        )
                for atw_unit in building.air_to_water_units:
                    self.atw_units[atw_unit.id] = atw_unit
                    if (
                        atw_unit.capabilities
                        and atw_unit.capabilities.has_energy_consumed_meter
                    ):
                        energy = await self.client.get_energy_telemetry(
                            atw_unit.id,
                            from_dt=start_of_month,
                            to_dt=utcnow(),
                        )
                        self.atw_energy[atw_unit.id] = sum(
                            float(e.value) for e in energy
                        )
        except MelCloudHomeAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except MelCloudHomeConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except MelCloudHomeTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
            ) from err
        else:
            return data

    @callback
    @override
    def _async_refresh_finished(self) -> None:
        """Notify entity callbacks after coordinator data has been updated."""
        if self.data is not None:
            self._notify_new_units(self.data)
