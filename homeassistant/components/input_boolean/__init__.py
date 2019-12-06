"""Support to keep track of user controlled booleans for within automation."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
from homeassistant.loader import bind_hass

DOMAIN = "input_boolean"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

_LOGGER = logging.getLogger(__name__)

CONF_INITIAL = "initial"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.Any(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_INITIAL): cv.boolean,
                    vol.Optional(CONF_ICON): cv.icon,
                },
                None,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RELOAD_SERVICE_SCHEMA = vol.Schema({})


@bind_hass
def is_on(hass, entity_id):
    """Test if input_boolean is True."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass, config):
    """Set up an input boolean."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = await _async_process_config(config)

    async def reload_service_handler(service_call):
        """Remove all input booleans and load new ones from config."""
        conf = await component.async_prepare_reload()
        if conf is None:
            return
        new_entities = await _async_process_config(conf)
        if new_entities:
            await component.async_add_entities(new_entities)

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")

    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")

    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")

    if entities:
        await component.async_add_entities(entities)

    return True


async def _async_process_config(config):
    """Process config and create list of entities."""
    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        initial = cfg.get(CONF_INITIAL)
        icon = cfg.get(CONF_ICON)

        entities.append(InputBoolean(object_id, name, initial, icon))

    return entities


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
