"""Support for local power state reporting of entities by emulating TP-Link Kasa smart plugs."""
import logging

from sense_energy import PlugInstance, SenseLink
import voluptuous as vol

from homeassistant.components.switch import ATTR_CURRENT_POWER_W
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template, is_template_string, result_as_boolean

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

    async def start_emulated_kasa(event):
        validate_configs(hass, entity_configs)
        try:
            await server.start()
        except OSError as error:
            _LOGGER.error("Failed to create UDP server at port 9999: %s", error)
        else:
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_emulated_kasa)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_emulated_kasa)

    return True


def validate_configs(hass, entity_configs):
    """Validate that entities exist and ensure templates are ready to use."""
    for entity_id, entity_config in entity_configs.items():
        state = hass.states.get(entity_id)
        if state is None:
            _LOGGER.warning("Entity not found: %s", entity_id)
            continue
        if CONF_POWER in entity_config:
            power_val = entity_config[CONF_POWER]
            if isinstance(power_val, str) and is_template_string(power_val):
                entity_config[CONF_POWER] = Template(power_val, hass)
            elif isinstance(power_val, Template):
                entity_config[CONF_POWER].hass = hass
        elif ATTR_CURRENT_POWER_W not in state.attributes:
            _LOGGER.warning("No power value defined for: %s", entity_id)


def get_plug_devices(hass, entity_configs):
    """Produce list of plug devices from config entities."""
    for entity_id, entity_config in entity_configs.items():
        state = hass.states.get(entity_id)
        if state is None:
            continue
        name = entity_config.get(CONF_NAME, state.name)

        if result_as_boolean(state.state):
            if CONF_POWER in entity_config:
                power_val = entity_config[CONF_POWER]
                if isinstance(power_val, (float, int)):
                    power = float(power_val)
                elif isinstance(power_val, str):
                    power = float(hass.states.get(power_val).state)
                elif isinstance(power_val, Template):
                    power = float(power_val.async_render())
            elif ATTR_CURRENT_POWER_W in state.attributes:
                power = float(state.attributes[ATTR_CURRENT_POWER_W])
        else:
            power = 0.0
        last_changed = state.last_changed.timestamp()
        yield PlugInstance(entity_id, start_time=last_changed, alias=name, power=power)
