"""Support for TPLink HS100/HS110/HS200 smart switch."""
from __future__ import annotations

import logging
from typing import Any, cast

from kasa import SmartDevice, SmartPlug

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import legacy_device_id
from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after
from .models import TPLinkData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = cast(SmartPlug, parent_coordinator.device)
    if not device.is_plug and not device.is_strip and not device.is_dimmer:
        return
    entities: list = []
    if device.is_strip:
        # Historically we only add the children if the device is a strip
        _LOGGER.debug("Initializing strip with %s sockets", len(device.children))
        for child in device.children:
            entities.append(SmartPlugSwitchChild(device, parent_coordinator, child))
    elif device.is_plug:
        entities.append(SmartPlugSwitch(device, parent_coordinator))

    # this will be removed on the led is implemented
    if hasattr(device, "led"):
        entities.append(SmartPlugLedSwitch(device, parent_coordinator))

    async_add_entities(entities)


class SmartPlugLedSwitch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of switch for the LED of a TPLink Smart Plug."""

    device: SmartPlug

    _attr_translation_key = "led"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, device: SmartPlug, coordinator: TPLinkDataUpdateCoordinator
    ) -> None:
        """Initialize the LED switch."""
        super().__init__(device, coordinator)
        self._attr_unique_id = f"{self.device.mac}_led"
        self._async_update_attrs()

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LED switch on."""
        await self.device.set_led(True)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LED switch off."""
        await self.device.set_led(False)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        is_on = self.device.led
        self._attr_is_on = is_on
        self._attr_icon = "mdi:led-on" if is_on else "mdi:led-off"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()


class SmartPlugSwitch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of a TPLink Smart Plug switch."""

    _attr_name: str | None = None

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        # For backwards compat with pyHS100
        self._attr_unique_id = legacy_device_id(device)
        self._async_update_attrs()

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.device.turn_on()

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.device.turn_off()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self.device.is_on

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()


class SmartPlugSwitchChild(SmartPlugSwitch):
    """Representation of an individual plug of a TPLink Smart Plug strip."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        plug: SmartDevice,
    ) -> None:
        """Initialize the child switch."""
        self._plug = plug
        super().__init__(device, coordinator)
        self._attr_unique_id = legacy_device_id(plug)
        self._attr_name = plug.alias

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the child switch on."""
        await self._plug.turn_on()

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the child switch off."""
        await self._plug.turn_off()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._plug.is_on
