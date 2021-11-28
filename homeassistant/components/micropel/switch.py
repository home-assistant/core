"""Support for Micropel switches."""
from __future__ import annotations

from abc import ABC
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    STATE_ON,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import SWITCH_SCHEMA
from .const import CONF_BIT_INDEX, CONF_HUB, CONF_PLC, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SWITCHES): vol.All(cv.ensure_list, [SWITCH_SCHEMA]),
    }
)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Read configuration and create Micropel switches."""
    switches = []

    for switch in config[CONF_SWITCHES]:
        hub_name = switch[CONF_HUB]
        hub = hass.data[DOMAIN][hub_name]
        switches.append(
            MicropelBaseSwitch(
                hub,
                switch[CONF_UNIQUE_ID],
                switch[CONF_NAME],
                switch.get(CONF_PLC),
                switch[CONF_ADDRESS],
                switch[CONF_BIT_INDEX],
            )
        )
    async_add_entities(switches)


class MicropelBaseSwitch(SwitchEntity, ToggleEntity, RestoreEntity, ABC):
    """Base class representing a Micropel switch."""

    def __init__(self, hub, unique_id, name, plc, address, bit_index):
        """Initialize the Micropel binary sensor."""
        self._hub = hub
        self._unique_id = unique_id
        self._name = name
        self._plc = int(plc)
        self._address = int(address)
        self._bit_index = int(bit_index)
        self._is_on = None
        self._available = True

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if not state:
            return
        self._is_on = state.state == STATE_ON

    @property
    def unique_id(self) -> str:
        """Return the uuid as the unique_id."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def turn_on(self, **kwargs):
        """Set switch on."""
        self._write_bit(True)

    def turn_off(self, **kwargs):
        """Set switch off."""
        self._write_bit(False)

    def update(self):
        """Update the state of the switch."""
        try:
            result = self._hub.read_bit(self._plc, self._address, self._bit_index)
            self._is_on = result
            self._available = True
        except Exception:
            self._available = False
            return

    def _write_bit(self, value: bool):
        """Update the state of the switch."""
        try:
            result = self._hub.write_bit(
                self._plc, self._address, self._bit_index, value
            )
            self._is_on = result
            self._available = True
        except Exception:
            self._available = False
            return
