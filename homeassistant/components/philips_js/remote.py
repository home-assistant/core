"""Remote control support for Apple TV."""

import asyncio

from haphilipsjs.typing import SystemType

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)

from . import LOGGER, PhilipsTVDataUpdateCoordinator
from .const import CONF_SYSTEM, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the configuration entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            PhilipsTVRemote(
                coordinator,
                config_entry.data[CONF_SYSTEM],
                config_entry.unique_id,
            )
        ]
    )


class PhilipsTVRemote(RemoteEntity):
    """Device that sends commands."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        system: SystemType,
        unique_id: str,
    ):
        """Initialize the Philips TV."""
        self._tv = coordinator.api
        self._coordinator = coordinator
        self._system = system
        self._unique_id = unique_id

    @property
    def name(self):
        """Return the device name."""
        return self._system["name"]

    @property
    def is_on(self):
        """Return true if device is on."""
        return bool(
            self._tv.on and (self._tv.powerstate == "On" or self._tv.powerstate is None)
        )

    @property
    def should_poll(self):
        """No polling needed for Apple TV."""
        return False

    @property
    def unique_id(self):
        """Return unique identifier if known."""
        return self._unique_id

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "name": self._system["name"],
            "identifiers": {
                (DOMAIN, self._unique_id),
            },
            "model": self._system.get("model"),
            "manufacturer": "Philips",
            "sw_version": self._system.get("softwareversion"),
        }

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        if self._tv.on and self._tv.powerstate:
            await self._tv.setPowerState("On")
        else:
            await self._coordinator.turn_on.async_run(self.hass, self._context)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        if self._tv.on:
            await self._tv.sendKey("Standby")
            self.async_write_ha_state()
        else:
            LOGGER.debug("Tv was already turned off")

    async def async_send_command(self, command, **kwargs):
        """Send a command to one device."""
        num_repeats = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        for _ in range(num_repeats):
            for single_command in command:
                LOGGER.debug("Sending command %s", single_command)
                await self._tv.sendKey(single_command)
                await asyncio.sleep(delay)
