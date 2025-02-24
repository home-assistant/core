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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.reload import async_get_platform_without_config_entry

from .const import (
    DOMAIN,
    FIRMWARE,
    NABU_CASA_FIRMWARE_RELEASES_URL,
    RADIO_DEVICE,
    RADIO_MANUFACTURER,
    RADIO_MODEL,
)

_LOGGER = logging.getLogger(__name__)


FIRMWARE_ENTITY_DESCRIPTIONS: dict[
    ApplicationType | None, FirmwareUpdateEntityDescription
] = {
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
    None: FirmwareUpdateEntityDescription(
        key="firmware",
        display_precision=0,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.DIAGNOSTIC,
        version_parser=lambda fw: fw,
        fw_type=None,
        version_key=None,
        expected_firmware_type=None,
        firmware_name=None,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the firmware update config entry."""
    firmware_type = config_entry.data[FIRMWARE]
    entity_description = FIRMWARE_ENTITY_DESCRIPTIONS[
        ApplicationType(firmware_type) if firmware_type is not None else None
    ]

    session = async_get_clientsession(hass)

    async_add_entities(
        [
            FirmwareUpdateEntity(
                device=RADIO_DEVICE,
                config_entry=config_entry,
                update_coordinator=FirmwareUpdateCoordinator(
                    hass,
                    session,
                    NABU_CASA_FIRMWARE_RELEASES_URL,
                ),
                entity_description=entity_description,
            )
        ]
    )


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

        self._attr_unique_id = f"yellow_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "yellow")},
            manufacturer=RADIO_MANUFACTURER,
            model=RADIO_MODEL,
        )

    def _update_config_entry_after_install(self, firmware_info: FirmwareInfo) -> None:
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data={
                **self._config_entry.data,
                FIRMWARE: firmware_info.firmware_type,
            },
        )

    def _firmware_type_changed(
        self, old_type: ApplicationType | None, new_type: ApplicationType | None
    ) -> None:
        # Remove the current entity when the firmware type changes
        ent_reg = er.async_get(self.hass)
        ent_reg.async_remove(self.entity_id)

        # And create a new one
        update_platform = async_get_platform_without_config_entry(
            self.hass, self._config_entry.domain, "update"
        )
        assert update_platform is not None

        new_entity = type(self)(
            self._current_device,
            self._config_entry,
            self.coordinator,
            FIRMWARE_ENTITY_DESCRIPTIONS[new_type],
        )
        update_platform.add_entities([new_entity], update_before_add=True)
