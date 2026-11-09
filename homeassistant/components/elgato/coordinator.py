"""DataUpdateCoordinator for Elgato."""

import asyncio
from dataclasses import dataclass
from typing import override

from elgato import (
    BatteryInfo,
    Elgato,
    ElgatoConnectionError,
    ElgatoError,
    FirmwareCatalog,
    FirmwareVersion,
    Info,
    Settings,
    State,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, FIRMWARE_SCAN_INTERVAL, LOGGER, SCAN_INTERVAL

type ElgatoConfigEntry = ConfigEntry[ElgatoDataUpdateCoordinator]


@dataclass
class ElgatoData:
    """Elgato data stored in the DataUpdateCoordinator."""

    battery: BatteryInfo | None
    info: Info
    settings: Settings
    state: State


class ElgatoDataUpdateCoordinator(DataUpdateCoordinator[ElgatoData]):
    """Class to manage fetching Elgato data."""

    config_entry: ElgatoConfigEntry
    has_battery: bool | None = None

    def __init__(self, hass: HomeAssistant, entry: ElgatoConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = Elgato(
            entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
        )
        # A firmware install gets the device to itself. It stops answering
        # while it erases a flash slot, and enough traffic during that window
        # takes its HTTP server down with it and restarts the light.
        self.device_lock = asyncio.Lock()
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> ElgatoData:
        """Fetch data from the Elgato device."""
        try:
            async with self.device_lock:
                if self.has_battery is None:
                    self.has_battery = await self.client.has_battery()

                return ElgatoData(
                    battery=await self.client.battery() if self.has_battery else None,
                    info=await self.client.info(),
                    settings=await self.client.settings(),
                    state=await self.client.state(),
                )
        except ElgatoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err
        except ElgatoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
            ) from err


class ElgatoFirmwareCoordinator(DataUpdateCoordinator[dict[int, FirmwareVersion]]):
    """Class to manage fetching the firmware Elgato ships.

    Elgato publishes one catalog covering every model, so this is shared by
    all Elgato devices rather than set up per config entry. It also lives on
    Elgato's servers rather than the local network, and changes a handful of
    times a year, so it runs on its own cadence.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the global Elgato firmware updater."""
        self.catalog = FirmwareCatalog(session=async_get_clientsession(hass))
        super().__init__(
            hass,
            LOGGER,
            config_entry=None,
            name=f"{DOMAIN}_firmware",
            update_interval=FIRMWARE_SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[int, FirmwareVersion]:
        """Fetch the firmware Elgato currently ships, per board type."""
        try:
            return await self.catalog.versions(refresh=True)
        except ElgatoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="firmware_communication_error",
            ) from err
        except ElgatoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="firmware_unknown_error",
            ) from err
