"""Support for Switchbot."""
import logging
from typing import Any, Dict

# pylint: disable=import-error, no-member
import switchbot
import voluptuous as vol

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchDevice,
)
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_MAC, CONF_SWITCHES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

SWITCH_SCHEMA = vol.Schema(
    {vol.Required(CONF_MAC): cv.string, vol.Optional(CONF_FRIENDLY_NAME): cv.string}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Switchbot devices."""
    devices = config.get(CONF_SWITCHES, {})
    switches = []

    for object_id, device_config in devices.items():
        switches.append(
            SwitchBot(
                object_id,
                device_config.get(CONF_FRIENDLY_NAME, object_id),
                device_config[CONF_MAC],
            )
        )

    if not switches:
        _LOGGER.error("No switches added")
        return False

    add_entities(switches)


class SwitchBot(SwitchDevice, RestoreEntity):
    """Representation of a Switchbot."""

    def __init__(self, object_id, friendly_name, mac) -> None:
        """Initialize the Switchbot."""
        self._state = None
        self._last_run_success = None
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = friendly_name
        self._mac = mac
        self._device = switchbot.Switchbot(mac=mac)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state == "on"

    def turn_on(self, **kwargs) -> None:
        """Turn device on."""
        if self._device.turn_on():
            self._state = True
            self._last_run_success = True
        else:
            self._last_run_success = False

    def turn_off(self, **kwargs) -> None:
        """Turn device off."""
        if self._device.turn_off():
            self._state = False
            self._last_run_success = True
        else:
            self._last_run_success = False

    @property
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        return True

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return self._mac.replace(":", "")

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return {"last_run_success": self._last_run_success}
