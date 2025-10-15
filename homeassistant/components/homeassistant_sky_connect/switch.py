"""Home Assistant SkyConnect switch entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.homeassistant_hardware.coordinator import (
    FirmwareUpdateCoordinator,
)
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

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


class BetaFirmwareSwitch(SwitchEntity, RestoreEntity):
    """Switch to enable beta firmware updates."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "beta_firmware"

    def __init__(
        self,
        coordinator: FirmwareUpdateCoordinator,
        config_entry: HomeAssistantSkyConnectConfigEntry,
    ) -> None:
        """Initialize the beta firmware switch."""
        self._coordinator = coordinator
        self._config_entry = config_entry

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

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to hass."""
        await super().async_added_to_hass()

        # Restore the last state
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
        else:
            self._attr_is_on = False

        # Apply the restored state to the coordinator
        await self._update_coordinator_prerelease()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on beta firmware updates."""
        self._attr_is_on = True
        self.async_write_ha_state()
        await self._update_coordinator_prerelease()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off beta firmware updates."""
        self._attr_is_on = False
        self.async_write_ha_state()
        await self._update_coordinator_prerelease()

    async def _update_coordinator_prerelease(self) -> None:
        """Update the coordinator with the current prerelease setting."""
        self._coordinator.client.update_prerelease(self._attr_is_on)
        await self._coordinator.async_refresh()
