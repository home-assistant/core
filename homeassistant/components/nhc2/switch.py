"""Support for NHC2 switches."""
import logging
from homeassistant.components.switch import SwitchDevice

from .helpers import nhc2_entity_processor
from nhc2_coco import CoCo, CoCoSwitch

from .const import DOMAIN, KEY_GATEWAY, BRAND, SWITCH

KEY_GATEWAY = KEY_GATEWAY
KEY_ENTITY = 'nhc2_switches'

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load NHC2 switches based on a config entry."""
    hass.data.setdefault(KEY_ENTITY, {})[config_entry.entry_id] = []
    gateway: CoCo = hass.data[KEY_GATEWAY][config_entry.entry_id]
    _LOGGER.debug('Platform is starting')
    gateway.get_switches(
        nhc2_entity_processor(hass,
                              config_entry,
                              async_add_entities,
                              KEY_ENTITY,
                              lambda x: NHC2HassSwitch(x))
    )


class NHC2HassSwitch(SwitchDevice):
    """Representation of an NHC2 Switch."""

    def __init__(self, nhc2switch: CoCoSwitch):
        """Initialize a switch."""
        self._nhc2switch = nhc2switch
        nhc2switch.on_change = self._on_change

    def _on_change(self):
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Pass - not in use."""
        pass

    def turn_on(self, **kwargs) -> None:
        """Pass - not in use."""
        pass

    async def async_turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        self._nhc2switch.turn_on()

    async def async_turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        self._nhc2switch.turn_off()

    def nhc2_update(self, nhc2switch: CoCoSwitch):
        """Update the NHC2 switch with a new object."""
        self._nhc2switch = nhc2switch
        nhc2switch.on_change = self._on_change
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return the lights UUID."""
        return self._nhc2switch.uuid

    @property
    def uuid(self):
        """Return the lights UUID."""
        return self._nhc2switch.uuid

    @property
    def should_poll(self):
        """Return false, since the light will push state."""
        return False

    @property
    def name(self):
        """Return the lights name."""
        return self._nhc2switch.name

    @property
    def available(self):
        """Return true if the light is online."""
        return self._nhc2switch.online

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._nhc2switch.is_on

    @property
    def device_info(self):
        """Return the device info."""
        return {
            'identifiers': {
                (DOMAIN, self.unique_id)
            },
            'name': self.name,
            'manufacturer': BRAND,
            'model': SWITCH,
            'via_hub': (DOMAIN, self._nhc2switch.profile_creation_id),
        }
