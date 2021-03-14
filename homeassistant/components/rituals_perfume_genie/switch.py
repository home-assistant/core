"""Support for Rituals Perfume Genie switches."""
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)

ON_STATE = "1"
AVAILABLE_STATE = 1

MANUFACTURER = "Rituals Cosmetics"
MODEL = "Diffuser"
ICON = "mdi:fan"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the diffuser switch."""
    account = hass.data[DOMAIN][config_entry.entry_id]
    diffusers = await account.get_devices()

    entities = []
    for diffuser in diffusers:
        entities.append(DiffuserSwitch(diffuser))

    async_add_entities(entities, True)


class DiffuserSwitch(SwitchEntity):
    """Representation of a diffuser switch."""

    def __init__(self, diffuser):
        """Initialize the switch."""
        self._diffuser = diffuser

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self._diffuser.data["hub"]["attributes"]["roomnamec"],
            "identifiers": {(DOMAIN, self._diffuser.data["hub"]["hublot"])},
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self._diffuser.data["hub"]["sensors"]["versionc"],
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._diffuser.data["hub"]["hublot"]

    @property
    def available(self):
        """Return if the device is available."""
        return self._diffuser.data["hub"]["status"] == AVAILABLE_STATE

    @property
    def name(self):
        """Return the name of the device."""
        return self._diffuser.data["hub"]["attributes"]["roomnamec"]

    @property
    def icon(self):
        """Return the icon of the device."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attributes = {
            "fan_speed": self._diffuser.data["hub"]["attributes"]["speedc"],
            "room_size": self._diffuser.data["hub"]["attributes"]["roomc"],
        }
        return attributes

    @property
    def is_on(self):
        """If the device is currently on or off."""
        return self._diffuser.data["hub"]["attributes"]["fanc"] == ON_STATE

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._diffuser.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._diffuser.turn_off()

    async def async_update(self):
        """Update the data of the device."""
        await self._diffuser.update_data()
