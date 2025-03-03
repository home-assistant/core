"""Home Assistant Yellow firmware update entity."""

from __future__ import annotations

import logging

import aiohttp

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    FIRMWARE,
    FIRMWARE_VERSION,
    NABU_CASA_FIRMWARE_RELEASES_URL,
    RADIO_DEVICE,
)

_LOGGER = logging.getLogger(__name__)


FIRMWARE_ENTITY_DESCRIPTIONS: dict[
    ApplicationType | None, FirmwareUpdateEntityDescription
] = {
    ApplicationType.EZSP: FirmwareUpdateEntityDescription(
        key="firmware",
        display_precision=0,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
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
        entity_category=EntityCategory.CONFIG,
        version_parser=lambda fw: fw.split("/", 1)[1].split("_", 1)[0],
        fw_type="yellow_openthread_rcp",
        version_key="ot_rcp_version",
        expected_firmware_type=ApplicationType.SPINEL,
        firmware_name="OpenThread RCP",
    ),
    None: FirmwareUpdateEntityDescription(
        key="firmware",
        display_precision=0,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        version_parser=lambda fw: fw,
        fw_type=None,
        version_key=None,
        expected_firmware_type=None,
        firmware_name=None,
    ),
}


def _async_create_update_entity(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    session: aiohttp.ClientSession,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> FirmwareUpdateEntity:
    """Create an update entity that handles firmware type changes."""
    firmware_type = config_entry.data[FIRMWARE]
    entity_description = FIRMWARE_ENTITY_DESCRIPTIONS[
        ApplicationType(firmware_type) if firmware_type is not None else None
    ]

    entity = FirmwareUpdateEntity(
        device=RADIO_DEVICE,
        config_entry=config_entry,
        update_coordinator=FirmwareUpdateCoordinator(
            hass,
            session,
            NABU_CASA_FIRMWARE_RELEASES_URL,
        ),
        entity_description=entity_description,
    )

    def firmware_type_changed(
        old_type: ApplicationType | None, new_type: ApplicationType | None
    ) -> None:
        """Replace the current entity when the firmware type changes."""
        er.async_get(hass).async_remove(entity.entity_id)
        async_add_entities(
            [
                _async_create_update_entity(
                    hass, config_entry, session, async_add_entities
                )
            ]
        )

    entity.async_on_remove(
        entity.add_firmware_type_changed_callback(firmware_type_changed)
    )

    return entity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the firmware update config entry."""
    session = async_get_clientsession(hass)
    entity = _async_create_update_entity(
        hass, config_entry, session, async_add_entities
    )

    async_add_entities([entity])


class FirmwareUpdateEntity(BaseFirmwareUpdateEntity):
    """Yellow firmware update entity."""

    bootloader_reset_type = "yellow"  # Triggers a GPIO reset

    def __init__(
        self,
        device: str,
        config_entry: ConfigEntry,
        update_coordinator: FirmwareUpdateCoordinator,
        entity_description: FirmwareUpdateEntityDescription,
    ) -> None:
        """Initialize the Yellow firmware update entity."""
        super().__init__(device, config_entry, update_coordinator, entity_description)

        self._attr_unique_id = self.entity_description.key

        # Use the cached firmware info if it exists
        if self._config_entry.data[FIRMWARE] is not None:
            self._current_firmware_info = FirmwareInfo(
                device=device,
                firmware_type=ApplicationType(self._config_entry.data[FIRMWARE]),
                firmware_version=self._config_entry.data[FIRMWARE_VERSION],
                owners=[],
                source="homeassistant_yellow",
            )

    @callback
    def _firmware_info_callback(self, firmware_info: FirmwareInfo) -> None:
        """Handle updated firmware info being pushed by an integration."""
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data={
                **self._config_entry.data,
                FIRMWARE: firmware_info.firmware_type,
                FIRMWARE_VERSION: firmware_info.firmware_version,
            },
        )
        super()._firmware_info_callback(firmware_info)
