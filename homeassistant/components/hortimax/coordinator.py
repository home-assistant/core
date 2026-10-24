"""Data update coordinator for the Ridder HortiMaX Pro (HortOS) integration."""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import override

from aiohortos import (
    Device,
    HortosAuthenticationError,
    HortosClient,
    HortosError,
    Readout,
    disambiguate_source_names,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, MANUFACTURER, SCAN_INTERVAL

type HortimaxConfigEntry = ConfigEntry[HortimaxCoordinator]


def source_key(source_type: str, source_name: str) -> str:
    """Return a stable key for a source within a controller."""
    return f"{source_type}::{source_name}"


def readout_key(source_type: str, source_name: str, identifier: str) -> str:
    """Return a stable key for a readout within a controller."""
    return f"{source_type}::{source_name}::{identifier}"


@dataclass
class HortimaxDeviceData:
    """All data for one greenhouse controller."""

    device: Device
    readouts: dict[str, Readout] = field(default_factory=dict)
    #: Source key -> de-duplicated display name.
    source_names: dict[str, str] = field(default_factory=dict)


class HortimaxCoordinator(DataUpdateCoordinator[dict[str, HortimaxDeviceData]]):
    """Poll the latest readout values of every controller."""

    config_entry: HortimaxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HortimaxConfigEntry,
        client: HortosClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.client = client

    @override
    async def _async_update_data(self) -> dict[str, HortimaxDeviceData]:
        """Fetch the latest value of every readout of every controller."""
        data: dict[str, HortimaxDeviceData] = {}
        try:
            # Read the controller list every cycle, so a controller added in
            # HortiMaX Pro is picked up without reloading the entry.
            devices = await self.client.get_devices()
            for device in devices:
                device_data = HortimaxDeviceData(device=device)
                sources: dict[str, tuple[str, str, str]] = {}
                for readout in await self.client.get_latest_readouts(device.name):
                    source = readout.source
                    key = readout_key(source.type, source.name, readout.identifier)
                    device_data.readouts[key] = readout
                    sources[source_key(source.type, source.name)] = (
                        source.display_name,
                        source.type,
                        source.name,
                    )
                device_data.source_names = disambiguate_source_names(sources)
                data[device.name] = device_data
                self._rename_changed_sources(device.name, device_data)
            # Only once the whole poll succeeded, so a readout failure does not
            # leave a registered controller behind for an update that is rejected.
            self._register_controllers(devices)
        except HortosAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except HortosError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
        return data

    @callback
    def _register_controllers(self, devices: list[Device]) -> None:
        """Register every controller, so its sources can point at it.

        Sources resolve their ``via_device_id`` from the registry when their
        first entity is added, so a controller has to be registered before the
        listeners that build those entities run. A controller carries no
        entities of its own, so nothing else would create it.
        """
        registry = dr.async_get(self.hass)
        for device in devices:
            registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                identifiers={(DOMAIN, device.name)},
                manufacturer=MANUFACTURER,
                name=device.label or device.name,
                model="HortiMaX Pro",
                serial_number=device.name,
            )

    @callback
    def _rename_changed_sources(
        self, device_id: str, device_data: HortimaxDeviceData
    ) -> None:
        """Follow a source that was renamed, or that now collides with another.

        Entities set the device name when they are first added, so a rename in
        HortiMaX Pro would otherwise not show until the entry is reloaded. A
        name the user set themselves takes precedence and is left alone.
        """
        registry = dr.async_get(self.hass)
        for key, name in device_data.source_names.items():
            device = registry.async_get_device_by_identifier(
                (DOMAIN, f"{device_id}::{key}"), self.config_entry.entry_id
            )
            if device is not None and device.name != name:
                registry.async_update_device(device.id, name=name)
