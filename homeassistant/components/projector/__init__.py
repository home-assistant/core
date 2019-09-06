"""Support for Projectors."""
import logging
from datetime import timedelta

from homeassistant.const import STATE_OFF, SERVICE_TURN_ON, SERVICE_TURN_OFF

from homeassistant.helpers.config_validation import (  # noqa
    ENTITY_SERVICE_SCHEMA,
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import bind_hass


_LOGGER = logging.getLogger(__name__)

DOMAIN = "projector"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(seconds=10)


STATE_COOLING = "cooling_down"
STATE_WARMING = "warming_up"


@bind_hass
def is_on(hass, entity_id=None):
    """
    Return true if specified projector entity_id is on.

    Check all projectors if no entity_id is specified.
    """
    entity_ids = [entity_id] if entity_id else hass.states.entity_ids(DOMAIN)
    return any(
        not hass.states.is_state(entity_id, STATE_OFF) for entity_id in entity_ids
    )


async def async_setup(hass, config):
    """Track states and offer events for media_players."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON, ENTITY_SERVICE_SCHEMA, "async_turn_on"
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, ENTITY_SERVICE_SCHEMA, "async_turn_off"
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class ProjectorDevice(Entity):
    """Representation of a projector."""

    @property
    def state(self):
        """State of the projector."""
        return None

    def turn_on(self):
        """Turn the projector on."""
        raise NotImplementedError()

    def async_turn_on(self):
        """Turn the projector on.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_on)

    def turn_off(self):
        """Turn the projector off."""
        raise NotImplementedError()

    def async_turn_off(self):
        """Turn the projector off.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_off)
