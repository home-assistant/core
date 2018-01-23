"""
Show custom ha-cards and sate-cards on Home Assistant frontend

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/custom_card/
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

        if ha_card is None and state_card is None:
            _LOGGER.error("Entity config must contain ha_card " +
                "and/or state_card ({}).".format(object_id))
            return False

        entities.append(CustomCard(object_id, ha_card, state_card,
            more_info_card, config))

    if not entities:
        return False

    yield from component.async_add_entities(entities)

    return True


class CustomCard(Entity):
    """Representation of a custom card."""

    def __init__(self, object_id, ha_card, state_card, more_info_card, config):
        """Initialize a custom card."""
        if ha_card:
            self.entity_id = ENTITY_ID_FORMAT_HA_CARD.format(object_id)
            self._state = ha_card
        else:
            self.entity_id = ENTITY_ID_FORMAT_STATE_CARD.format(object_id)
            self._state = state_card
        
        self._attributes = {}
        if ha_card:
            self._attributes['ha_card'] = ha_card
        if state_card:
            self._attributes['state_card'] = state_card
        if more_info_card:
            self._attributes['more_info_card'] = more_info_card
        if config:
            self._attributes['config'] = config

    @property
    def state(self):
        """Return card as state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes
