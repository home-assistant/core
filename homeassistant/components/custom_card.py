"""
Show custom full-cards (ha-cards) and sate-cards on Home Assistant frontend.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/custom_card/
"""
import asyncio
import json
import logging

import voluptuous as vol

from homeassistant.components import http
from homeassistant.const import HTTP_BAD_REQUEST
import homeassistant.helpers.config_validation as cv

DOMAIN = 'custom_card'
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

CONF_FULL_CARD = 'full_card'
CONF_STATE_CARD = 'state_card'
CONF_MORE_INFO_CARD = 'more_info_card'
CONF_CONFIG = 'config'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Any({
            vol.Optional(CONF_FULL_CARD): cv.string,
            vol.Optional(CONF_STATE_CARD): cv.string,
            vol.Optional(CONF_MORE_INFO_CARD): cv.string,
            vol.Optional(CONF_CONFIG): cv.match_all,
        }, None)
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize custom card."""
    card_configs = {}

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        full_card = cfg.get(CONF_FULL_CARD)
        state_card = cfg.get(CONF_STATE_CARD)
        more_info_card = cfg.get(CONF_MORE_INFO_CARD)
        config = cfg.get(CONF_CONFIG)

        if full_card is None and state_card is None:
            _LOGGER.error("Entity config must contain full_card " +
                          "and/or state_card (%s)", object_id)
            return False

        if full_card:
            entity_id = 'custom_full_card.{}'.format(object_id)
            state = full_card
        else:
            entity_id = 'custom_state_card.{}'.format(object_id)
            state = state_card

        attributes = {}
        if full_card:
            attributes['custom_ui_full_card'] = full_card
        if state_card:
            attributes['custom_ui_state_card'] = state_card
        if more_info_card:
            attributes['custom_ui_more_info_card'] = more_info_card

        if config:
            card_configs[entity_id] = json.dumps(config)

        hass.states.async_set(entity_id, state, attributes)

    hass.http.register_view(CustomCardView(card_configs))

    return True


class CustomCardView(http.HomeAssistantView):
    """API to request card config."""

    url = '/api/custom_card'
    name = 'api:custom_card'

    def __init__(self, card_configs):
        """Initialize a custom card view."""
        self._card_configs = card_configs

    @http.RequestDataValidator(vol.Schema({
        vol.Required('entity_id'): str,
    }))
    @asyncio.coroutine
    def post(self, request, data):
        """Handle a config request."""
        try:
            config = self._card_configs[data['entity_id']]
        except KeyError:
            return self.json_message('For this entity is no config available.',
                                     HTTP_BAD_REQUEST)
        else:
            return self.json({'config': config})
