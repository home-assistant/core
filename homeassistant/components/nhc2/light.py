"""Support for NHC2 lights."""
import logging
from typing import List
from homeassistant.components.light import Light

from .helpers import nhc2_entity_processor
from nhc2_coco import CoCoLight, CoCo

from .const import DOMAIN, KEY_GATEWAY, BRAND, LIGHT

KEY_GATEWAY = KEY_GATEWAY
KEY_ENTITY = 'nhc2_lights'

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    hass.data.setdefault(KEY_ENTITY, {})[config_entry.entry_id]: List = []
    gateway: CoCo = hass.data[KEY_GATEWAY][config_entry.entry_id]
    _LOGGER.debug('Platform is starting')
    gateway.get_lights(
        nhc2_entity_processor(hass, config_entry, async_add_entities, KEY_ENTITY, lambda x: NHC2HassLight(x))
    )


class NHC2HassLight(Light):
    """Representation of an NHC2 Light."""

    def __init__(self, nhc2light: CoCoLight):
        self._nhc2light = nhc2light
        nhc2light.on_change = self._on_change

    def _on_change(self):
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        pass

    def turn_on(self, **kwargs) -> None:
        pass

    async def async_turn_on(self, **kwargs):
        self._nhc2light.turn_on()

    async def async_turn_off(self, **kwargs):
        self._nhc2light.turn_off()

    def nhc2_update(self, nhc2light: CoCoLight):
        self._nhc2light = nhc2light
        nhc2light.on_change = self._on_change
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        return self._nhc2light.uuid

    @property
    def uuid(self):
        return self._nhc2light.uuid

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._nhc2light.name

    @property
    def available(self):
        return self._nhc2light.online

    @property
    def is_on(self):
        return self._nhc2light.is_on

    @property
    def device_info(self):
        """Return the device info."""
        return {
            'identifiers': {
                (DOMAIN, self.unique_id)
            },
            'name': self.name,
            'manufacturer': BRAND,
            'model': LIGHT,
            'via_hub': (DOMAIN, self._nhc2light.profile_creation_id),
        }
