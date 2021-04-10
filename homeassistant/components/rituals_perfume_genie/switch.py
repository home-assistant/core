"""Support for Rituals Perfume Genie switches."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from .const import ATTRIBUTES, COORDINATORS, DEVICES, DOMAIN, HUB
from .entity import DiffuserEntity

STATUS = "status"
FAN = "fanc"
SPEED = "speedc"
ROOM = "roomc"

ON_STATE = "1"
AVAILABLE_STATE = 1


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the diffuser switch."""
    diffusers = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities = []
    for hublot, diffuser in diffusers.items():
        coordinator = coordinators[hublot]
        entities.append(DiffuserSwitch(diffuser, coordinator))

    async_add_entities(entities)


class DiffuserSwitch(SwitchEntity, DiffuserEntity):
    """Representation of a diffuser switch."""

    def __init__(self, diffuser, coordinator):
        """Initialize the diffuser switch."""
        super().__init__(diffuser, coordinator, "")
        self._is_on = self.coordinator.data[HUB][ATTRIBUTES][FAN] == ON_STATE

    @property
    def available(self):
        """Return if the device is available."""
        return self.coordinator.data[HUB][STATUS] == AVAILABLE_STATE

    @property
    def icon(self):
        """Return the icon of the device."""
        return "mdi:fan"

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attributes = {
            "fan_speed": self.coordinator.data[HUB][ATTRIBUTES][SPEED],
            "room_size": self.coordinator.data[HUB][ATTRIBUTES][ROOM],
        }
        return attributes

    @property
    def is_on(self):
        """If the device is currently on or off."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._diffuser.turn_on()
        self._is_on = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._diffuser.turn_off()
        self._is_on = False
        self.schedule_update_ha_state()

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._is_on = self.coordinator.data[HUB][ATTRIBUTES][FAN] == ON_STATE
        self.async_write_ha_state()
