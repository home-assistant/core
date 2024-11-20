"""Support for Lutron Homeworks binary sensors."""

from __future__ import annotations

import logging
from typing import Any

from pyhomeworks.pyhomeworks import HW_KEYPAD_LED_CHANGED, Homeworks

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeworksData, HomeworksKeypad
from .const import (
    CONF_ADDR,
    CONF_BUTTONS,
    CONF_CONTROLLER_ID,
    CONF_KEYPADS,
    CONF_LED,
    CONF_NUMBER,
    DOMAIN,
)
from .entity import HomeworksEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Homeworks binary sensors."""
    data: HomeworksData = hass.data[DOMAIN][entry.entry_id]
    controller = data.controller
    controller_id = entry.options[CONF_CONTROLLER_ID]
    entities = []
    for keypad in entry.options.get(CONF_KEYPADS, []):
        for button in keypad[CONF_BUTTONS]:
            if not button[CONF_LED]:
                continue
            entity = HomeworksBinarySensor(
                controller,
                data.keypads[keypad[CONF_ADDR]],
                controller_id,
                keypad[CONF_ADDR],
                keypad[CONF_NAME],
                button[CONF_NAME],
                button[CONF_NUMBER],
            )
            entities.append(entity)
    async_add_entities(entities, True)


class HomeworksBinarySensor(HomeworksEntity, BinarySensorEntity):
    """Homeworks Binary Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        controller: Homeworks,
        keypad: HomeworksKeypad,
        controller_id: str,
        addr: str,
        keypad_name: str,
        button_name: str,
        led_number: int,
    ) -> None:
        """Create device with Addr, name, and rate."""
        super().__init__(controller, controller_id, addr, led_number, button_name)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{controller_id}.{addr}")}, name=keypad_name
        )
        self._keypad = keypad

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        signal = f"homeworks_entity_{self._controller_id}_{self._addr}"
        _LOGGER.debug("connecting %s", signal)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._update_callback)
        )
        await self._keypad.request_keypad_led_states()

    @callback
    def _update_callback(self, msg_type: str, values: list[Any]) -> None:
        """Process device specific messages."""
        if msg_type != HW_KEYPAD_LED_CHANGED or len(values[1]) < self._idx:
            return
        self._attr_is_on = bool(values[1][self._idx - 1])
        self.async_write_ha_state()
