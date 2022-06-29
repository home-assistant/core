"""Support for TPLink HS100/HS110/HS200 smart switch."""
from __future__ import annotations

import logging
from typing import Any, cast

from kasa import SmartDevice, SmartPlug

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import legacy_device_id
from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator: TPLinkDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device = cast(SmartPlug, coordinator.device)
    if not device.is_plug and not device.is_strip and not device.is_dimmer:
        return
    entities: list = []
    if device.is_strip:
        # Historically we only add the children if the device is a strip
        _LOGGER.debug("Initializing strip with %s sockets", len(device.children))
        for child in device.children:
            entities.append(SmartPlugSwitch(child, coordinator))
    elif device.is_plug:
        entities.append(SmartPlugSwitch(device, coordinator))

    entities.append(SmartPlugLedSwitch(device, coordinator))

    async_add_entities(entities)


class SmartPlugLedSwitch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of switch for the LED of a TPLink Smart Plug."""

    device: SmartPlug

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, device: SmartPlug, coordinator: TPLinkDataUpdateCoordinator
    ) -> None:
        """Initialize the LED switch."""
        super().__init__(device, coordinator)

        self._attr_name = f"{device.alias} LED"
        self._attr_unique_id = f"{self.device.mac}_led"

    @property
    def icon(self) -> str:
        """Return the icon for the LED."""
        return "mdi:led-on" if self.is_on else "mdi:led-off"

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LED switch on."""
        await self.device.set_led(True)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LED switch off."""
        await self.device.set_led(False)

    @property
    def is_on(self) -> bool:
        """Return true if LED switch is on."""
        return bool(self.device.led)


class SmartPlugSwitch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        # For backwards compat with pyHS100
        self._attr_unique_id = legacy_device_id(device)

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.device.turn_on()

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.device.turn_off()
