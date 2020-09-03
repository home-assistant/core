"""Support for local power state reporting of entities by emulating TP-Link Kasa smart plugs."""
import logging
from time import time

from sense_energy import PlugInstance, SenseLink
import voluptuous as vol

from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_ENTITIES,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template, is_template_string

from .const import CONF_POWER, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_POWER): vol.Any(
            vol.Coerce(float),
            cv.template,
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ENTITIES): vol.Schema(
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
    entity_configs = conf.get(CONF_ENTITIES, {})

    def devices():
        """Devices to be emulated."""
        yield from get_plug_devices(hass, entity_configs)

    server = SenseLink(devices)

    async def stop_emulated_kasa(event):
        await server.stop()

    try:
        await server.start()
    except OSError as error:
        _LOGGER.error("Failed to create UDP server at port 9999: %s", error)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_emulated_kasa)

    return True


def get_plug_devices(hass, entity_configs):
    """Produce list of plug devices from config entities."""
    for entity_id, entity_config in entity_configs:
        state = hass.states.get(entity_id)
        if state is None:
            continue
        name = entity_config.get(CONF_NAME, state.name)

        if state.state == STATE_ON:
            power_val = entity_config[CONF_POWER]
            if isinstance(power_val, (float, int)):
                power = float(power_val)
            elif isinstance(power_val, str):
                if is_template_string(power_val):
                    power = float(Template(power_val, hass).async_render())
                else:
                    power = float(hass.states.get(power_val).state)
            elif isinstance(power_val, Template):
                power_val.hass = hass
                power = float(power_val.async_render())

            if state.last_changed:
                last_changed = state.last_changed.timestamp()
            else:
                last_changed = time() - 1
        else:
            power = 0.0
            last_changed = time()
        yield PlugInstance(entity_id, start_time=last_changed, alias=name, power=power)
