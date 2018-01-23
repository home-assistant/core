"""
Show custom ha-cards and sate-cards on Home Assistant frontend
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
import homeassistant.helpers.config_validation as cv

DOMAIN = 'custom_card'

ENTITY_ID_FORMAT_HA_CARD = 'custom_ha_card' + '.{}'
ENTITY_ID_FORMAT_STATE_CARD = 'custom_state_card' + '.{}'

_LOGGER = logging.getLogger(__name__)

CONF_HA_CARD = 'ha_card'
CONF_STATE_CARD = 'state_card'
CONF_MORE_INFO_CARD = 'more_info_card'
CONF_CONFIG = 'config'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Any({
            vol.Optional(CONF_HA_CARD): cv.string,
            vol.Optional(CONF_STATE_CARD): cv.string,
            vol.Optional(CONF_MORE_INFO_CARD): cv.string,
            vol.Optional(CONF_CONFIG): cv.match_all,
        }, None)
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize custom card."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        ha_card = cfg.get(CONF_HA_CARD)
        state_card = cfg.get(CONF_STATE_CARD)
        more_info_card = cfg.get(CONF_MORE_INFO_CARD)
        config = cfg.get(CONF_CONFIG)
        entities.append(CustomCard(object_id, ha_card, state_card, more_info_card, config))


    if not entities:
        return False    

    yield from component.async_add_entities(entities)

    return True

class CustomCard(Entity):
    """Representation of a custom card."""

    def __init__(self, object_id, ha_card, state_card, more_info_card, config):
        """Initialize a boolean input."""
        self._ha_card = ha_card
        self._state_card = state_card
        if self._ha_card:
            self.entity_id = ENTITY_ID_FORMAT_HA_CARD.format(object_id)
        else:
            self.entity_id = ENTITY_ID_FORMAT_STATE_CARD.format(object_id)
        self._more_info_card = more_info_card
        self._config = config

    @property
    def state(self):
        """Return card as state."""
        if self._ha_card:
            return self._ha_card
        return self._state_card

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        _attributes = {}
        if self._ha_card:
            _attributes['ha_card'] = self._ha_card
        if self._state_card:
            _attributes['state_card'] = self._state_card
        if self._more_info_card:
            _attributes['more_info_card'] = self._more_info_card
        if self._config:
            _attributes['config'] = self._config
        return _attributes
