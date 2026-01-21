"""Home Assistant SkyConnect switch entities."""

from __future__ import annotations

import logging

from homeassistant.components.homeassistant_hardware.coordinator import (
    FirmwareUpdateCoordinator,
)
from homeassistant.components.homeassistant_hardware.switch import (
    BaseBetaFirmwareSwitch,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeAssistantSkyConnectConfigEntry
from .const import DOMAIN, PRODUCT, SERIAL_NUMBER, HardwareVariant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeAssistantSkyConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform for Home Assistant SkyConnect."""
    async_add_entities(
        [BetaFirmwareSwitch(config_entry.runtime_data.coordinator, config_entry)]
    )


class BetaFirmwareSwitch(BaseBetaFirmwareSwitch):
    """Home Assistant SkyConnect beta firmware switch."""

    def __init__(
        self,
        coordinator: FirmwareUpdateCoordinator,
        config_entry: HomeAssistantSkyConnectConfigEntry,
    ) -> None:
        """Initialize the beta firmware switch."""
        super().__init__(coordinator, config_entry)

        variant = HardwareVariant.from_usb_product_name(
            self._config_entry.data[PRODUCT]
        )
        serial_number = self._config_entry.data[SERIAL_NUMBER]

        self._attr_unique_id = f"{serial_number}_beta_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"{variant.full_name} ({serial_number[:8]})",
            model=variant.full_name,
            manufacturer="Nabu Casa",
            serial_number=serial_number,
        )
