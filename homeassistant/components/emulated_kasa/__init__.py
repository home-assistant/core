"""Support for local power state reporting of entities by emulating TP-Link Kasa smart plugs."""
import logging
from time import time

from sense_energy import PlugInstance, SenseLink

import voluptuous as vol

import homeassistant.components as comps
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, 
    CONF_ENTITIES, 
    CONF_NAME, 
    EVENT_HOMEASSISTANT_STOP
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import CONF_POWER, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_POWER): vol.Any(vol.Coerce(float), cv.template,),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ENTITIES): vol.Schema(
                    {cv.entity_id: CONFIG_ENTITY_SCHEMA}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Sense component."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)
    if not conf:
        return True
    hass.data[DOMAIN][CONF_ENTITIES] = conf.get(CONF_ENTITIES, {})

    def devices():
        """Drvices to be emulated."""
        yield from get_plug_devices(hass)

    server = SenseLink(devices)
    async def start_emulated_kasa(event):
        await server.stop()
        
    try:
        await server.start()
    except OSError as error:
        _LOGGER.error(
            "Failed to create UDP server at port 9999: %s", error
        )
    else:
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, start_emulated_kasa
        )

    return True


def get_plug_devices(hass):
    """Produce list of plug devices from config entities."""
    entities = hass.data[DOMAIN][CONF_ENTITIES]
    for entity_id in entities:
        state = hass.states.get(entity_id)
        if state is None:
            continue
        name = state.attributes.get(ATTR_FRIENDLY_NAME, entity_id)
        name = entities[entity_id].get(CONF_NAME, name)

        if comps.is_on(hass, entity_id):
            try:
                power = float(entities[entity_id][CONF_POWER])
            except TypeError:
                entities[entity_id][CONF_POWER].hass = hass
                power = float(entities[entity_id][CONF_POWER].async_render())

            if state.last_changed:
                last_changed = state.last_changed.timestamp()
            else:
                last_changed = time() - 1
        else:
            power = 0.0
            last_changed = time()
        yield PlugInstance(entity_id, start_time=last_changed, alias=name, power=power)


    
