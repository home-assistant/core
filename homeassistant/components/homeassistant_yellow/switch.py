"""Home Assistant Yellow switch entities."""

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

from . import HomeAssistantYellowConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeAssistantYellowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform for Home Assistant Yellow."""
    async_add_entities(
        [BetaFirmwareSwitch(config_entry.runtime_data.coordinator, config_entry)]
    )


class BetaFirmwareSwitch(BaseBetaFirmwareSwitch):
    """Home Assistant Yellow beta firmware switch."""

    def __init__(
        self,
        coordinator: FirmwareUpdateCoordinator,
        config_entry: HomeAssistantYellowConfigEntry,
    ) -> None:
        """Initialize the beta firmware switch."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = "beta_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "yellow")},
            name=MODEL,
            model=MODEL,
            manufacturer=MANUFACTURER,
        )
