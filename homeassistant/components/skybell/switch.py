"""Switch support for the Skybell HD Doorbell."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from . import SkybellDevice
from .const import DATA_COORDINATOR, DATA_DEVICES, DOMAIN, SWITCH_TYPES

PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
                vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
                    cv.ensure_list, [vol.In(SWITCH_TYPES)]
                ),
            }
        )
    )
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the SkyBell switch."""
    skybell_data = hass.data[DOMAIN][entry.entry_id]
    switches = []
    for switch in SWITCH_TYPES:
        for device in skybell_data[DATA_DEVICES]:
            switches.append(
                SkybellSwitch(
                    skybell_data[DATA_COORDINATOR],
                    device,
                    switch,
                    entry.entry_id,
                )
            )

    async_add_entities(switches)


class SkybellSwitch(SkybellDevice, SwitchEntity):
    """A switch implementation for Skybell devices."""

    def __init__(
        self,
        coordinator,
        device,
        switch,
        server_unique_id,
    ):
        """Initialize a SkyBell switch."""
        super().__init__(coordinator, device, switch, server_unique_id)
        self._name = f"{device.name} {SWITCH_TYPES[switch]}"

        self._switch = switch
        self._device = device

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the switch."""
        return f"{self._server_unique_id}/{self._switch}"

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        setattr(self._device, self._switch, True)

    def turn_off(self, **kwargs):
        """Turn off the switch."""
        setattr(self._device, self._switch, False)

    @property
    def is_on(self):
        """Return true if device is on."""
        return getattr(self._device, self._switch)
