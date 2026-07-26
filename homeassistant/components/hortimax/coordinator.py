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
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL
from .naming import disambiguate_source_names

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
    devices: list[Device]

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
    async def _async_setup(self) -> None:
        """Discover the available controllers once."""
        try:
            self.devices = await self.client.get_devices()
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

    @override
    async def _async_update_data(self) -> dict[str, HortimaxDeviceData]:
        """Fetch the latest value of every readout of every controller."""
        data: dict[str, HortimaxDeviceData] = {}
        try:
            for device in self.devices:
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
