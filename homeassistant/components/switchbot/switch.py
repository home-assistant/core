"""Support for Switchbot bot."""
from __future__ import annotations

from typing import Any

# pylint: disable=import-error
import switchbot
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ATTR_BOT, DEFAULT_NAME, DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import yaml config and initiates config flow for Switchbot devices."""

    # Check if entry config exists and skips import if it does.
    if hass.config_entries.async_entries(DOMAIN):
        return

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Switchbot based on a config entry."""

    switchbot_config_entries = hass.config_entries.async_entries(DOMAIN)

    switchbot_bot_entries = [
        item
        for item in switchbot_config_entries
        if item.data[CONF_SENSOR_TYPE] == ATTR_BOT
    ]

    devices = []

    for device in switchbot_bot_entries:
        devices.append(
            SwitchBot(
                device.data[CONF_MAC],
                device.data[CONF_NAME],
                device.data.get(CONF_PASSWORD, None),
            )
        )

    async_add_entities(devices)


class SwitchBot(SwitchEntity, RestoreEntity):
    """Representation of a Switchbot."""

    def __init__(self, mac, name, password=None) -> None:
        """Initialize the Switchbot."""

        self._state: bool | None = None
        self._last_run_success: bool | None = None
        self._name = name
        self._mac = mac
        self._device = switchbot.Switchbot(mac=mac, password=password)

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
        return bool(self._state)

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._mac.replace(":", "")

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {"last_run_success": self._last_run_success}
