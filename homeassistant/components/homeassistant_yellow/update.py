"""Home Assistant Yellow firmware update entity."""

from __future__ import annotations

import logging

from homeassistant.components.homeassistant_hardware.coordinator import (
    FirmwareUpdateCoordinator,
)
from homeassistant.components.homeassistant_hardware.update import (
    BaseFirmwareUpdateEntity,
    FirmwareUpdateEntityDescription,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.components.update import UpdateDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the firmware update config entry."""

    session = async_get_clientsession(hass)

    async_add_entities(
        [
            FirmwareUpdateEntity(
                device=config_entry.data["device"],
                config_entry=config_entry,
                update_coordinator=FirmwareUpdateCoordinator(hass, session),
            )
        ]
    )


class FirmwareUpdateEntity(BaseFirmwareUpdateEntity):
    """Yellow firmware update entity."""

    firmware_entity_descriptions = {
        ApplicationType.EZSP: FirmwareUpdateEntityDescription(
            key="firmware",
            display_precision=0,
            device_class=UpdateDeviceClass.FIRMWARE,
            entity_category=EntityCategory.DIAGNOSTIC,
            version_parser=lambda fw: fw.split(" ", 1)[0],
            fw_type="yellow_zigbee_ncp",
            version_key="ezsp_version",
            expected_firmware_type=ApplicationType.EZSP,
            firmware_name="EmberZNet",
        ),
        ApplicationType.SPINEL: FirmwareUpdateEntityDescription(
            key="firmware",
            display_precision=0,
            device_class=UpdateDeviceClass.FIRMWARE,
            entity_category=EntityCategory.DIAGNOSTIC,
            version_parser=lambda fw: fw.split("/", 1)[1].split("_", 1)[0],
            fw_type="yellow_openthread_rcp",
            version_key="ot_rcp_version",
            expected_firmware_type=ApplicationType.SPINEL,
            firmware_name="OpenThread RCP",
        ),
    }

    bootloader_reset_type = "yellow"

    def __init__(
        self,
        device: str,
        config_entry: ConfigEntry,
        update_coordinator: FirmwareUpdateCoordinator,
    ) -> None:
        """Initialize the Yellow firmware update entity."""
        super().__init__(device, config_entry, update_coordinator)

        self._attr_unique_id = f"yellow_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "yellow")},
            manufacturer="Nabu Casa",
            model="Home Assistant Yellow",
        )

    def _update_config_entry_after_install(self, firmware_info: FirmwareInfo) -> None:
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data={
                **self._config_entry.data,
                "firmware": firmware_info.firmware_type,
            },
        )
