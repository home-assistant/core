"""Coordinator for the energieleser integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import override

from energieleser import (
    DeviceType,
    EnergieleserClient,
    EnergieleserConnectionError,
    EnergieleserDevice,
    EnergieleserError,
    EnergieleserUnknownDeviceError,
    StromleserOneDevice,
    get_latest_firmware_versions,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(seconds=10)
FIRMWARE_SCAN_INTERVAL = timedelta(hours=6)

type EnergieleserConfigEntry = ConfigEntry[EnergieleserData]


class EnergieleserCoordinator(DataUpdateCoordinator[EnergieleserDevice]):
    """Coordinator that polls a single energieleser device."""

    config_entry: EnergieleserConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EnergieleserConfigEntry,
        client: EnergieleserClient,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device_id = config_entry.data[CONF_DEVICE_ID]

    @override
    async def _async_update_data(self) -> EnergieleserDevice:
        """Fetch data from the energieleser device API."""
        try:
            device = await self.client.get_device()
        except EnergieleserUnknownDeviceError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_device",
                translation_placeholders={
                    "device_id": self.device_id,
                },
            ) from err
        except EnergieleserConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={
                    "device_id": self.device_id,
                },
            ) from err
        except EnergieleserError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={
                    "device_id": self.device_id,
                },
            ) from err
        if isinstance(device, StromleserOneDevice):
            issue_id = f"pin_locked_{self.config_entry.entry_id}"
            if device.pin_locked:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    is_persistent=False,
                    learn_more_url="https://docs.energieleser.de/en/docs/stromleser-one/installation/preparation",
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="meter_locked",
                    translation_placeholders={
                        "device_name": self.config_entry.title,
                    },
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)

        return device


class EnergieleserFirmwareCoordinator(DataUpdateCoordinator[dict[DeviceType, str]]):
    """Coordinator for the latest firmware versions, shared by all entries."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=None,
            name=f"{DOMAIN}_firmware",
            update_interval=FIRMWARE_SCAN_INTERVAL,
        )
        self._session = async_get_clientsession(hass)

    @override
    async def _async_update_data(self) -> dict[DeviceType, str]:
        """Fetch the latest firmware versions from the OTA server."""
        try:
            return await get_latest_firmware_versions(self._session)
        except EnergieleserError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="firmware_check_failed",
            ) from err


@dataclass
class EnergieleserData:
    """Runtime data for an energieleser config entry."""

    device_coordinator: EnergieleserCoordinator
    firmware_coordinator: EnergieleserFirmwareCoordinator
