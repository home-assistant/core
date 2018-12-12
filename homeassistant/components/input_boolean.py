"""
Component to keep track of user controlled booleans for within automation.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/input_boolean/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_ICON, CONF_NAME, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_TOGGLE, STATE_ON)
from homeassistant.loader import bind_hass
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity

DOMAIN = 'input_boolean'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

_LOGGER = logging.getLogger(__name__)

CONF_INITIAL = 'initial'

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Any({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_INITIAL): cv.boolean,
            vol.Optional(CONF_ICON): cv.icon,
        }, None)
    })
}, extra=vol.ALLOW_EXTRA)


@bind_hass
def is_on(hass, entity_id):
    """Test if input_boolean is True."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass, config):
    """Set up an input boolean."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        initial = cfg.get(CONF_INITIAL)
        icon = cfg.get(CONF_ICON)

        entities.append(InputBoolean(object_id, name, initial, icon))

    if not entities:
        return False

    component.async_register_entity_service(
        SERVICE_TURN_ON, SERVICE_SCHEMA,
        'async_turn_on'
    )

    component.async_register_entity_service(
        SERVICE_TURN_OFF, SERVICE_SCHEMA,
        'async_turn_off'
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE, SERVICE_SCHEMA,
        'async_toggle'
    )

    await component.async_add_entities(entities)
    return True


class InputBoolean(ToggleEntity, RestoreEntity):
    """Representation of a boolean input."""

    def __init__(self, object_id, name, initial, icon):
        """Initialize a boolean input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._state = initial
        self._icon = icon

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return name of the boolean input."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def is_on(self):
        """Return true if entity is on."""
        return self._state

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        # If not None, we got an initial value.
        await super().async_added_to_hass()
        if self._state is not None:
            return

        state = await self.async_get_last_state()
        self._state = state and state.state == STATE_ON

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = True
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = False
        await self.async_update_ha_state()
