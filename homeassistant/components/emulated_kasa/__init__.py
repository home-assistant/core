"""Support for local power state reporting of entities by emulating TP-Link Kasa smart plugs."""
import logging

from sense_energy import PlugInstance, SenseLink
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import ATTR_CURRENT_POWER_W
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.template import Template, is_template_string

from .const import CONF_POWER, CONF_POWER_ENTITY, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_POWER): vol.Any(
            vol.Coerce(float),
            cv.template,
        ),
        vol.Optional(CONF_POWER_ENTITY): cv.string,
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
    """Set up the emulated_kasa component."""
    conf = config.get(DOMAIN)
    if not conf:
        return True
    entity_configs = conf[CONF_ENTITIES]

    def devices():
        """Devices to be emulated."""
        yield from get_plug_devices(hass, entity_configs)

    server = SenseLink(devices)

    async def stop_emulated_kasa(event):
        await server.stop()

    async def start_emulated_kasa(event):
        await validate_configs(hass, entity_configs)
        try:
            await server.start()
        except OSError as error:
            _LOGGER.error("Failed to create UDP server at port 9999: %s", error)
        else:
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_emulated_kasa)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_emulated_kasa)

    return True


async def validate_configs(hass, entity_configs):
    """Validate that entities exist and ensure templates are ready to use."""
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    for entity_id, entity_config in entity_configs.items():
        state = hass.states.get(entity_id)
        if state is None:
            _LOGGER.debug("Entity not found: %s", entity_id)
            continue

        entity = entity_registry.async_get(entity_id)
        if entity:
            entity_config[CONF_UNIQUE_ID] = get_system_unique_id(entity)
        else:
            entity_config[CONF_UNIQUE_ID] = entity_id

        if CONF_POWER in entity_config:
            power_val = entity_config[CONF_POWER]
            if isinstance(power_val, str) and is_template_string(power_val):
                entity_config[CONF_POWER] = Template(power_val, hass)
            elif isinstance(power_val, Template):
                entity_config[CONF_POWER].hass = hass
        elif CONF_POWER_ENTITY in entity_config:
            power_val = entity_config[CONF_POWER_ENTITY]
            if hass.states.get(power_val) is None:
                _LOGGER.debug("Sensor Entity not found: %s", power_val)
            else:
                entity_config[CONF_POWER] = power_val
        elif state.domain == SENSOR_DOMAIN:
            pass
        elif ATTR_CURRENT_POWER_W in state.attributes:
            pass
        else:
            _LOGGER.debug("No power value defined for: %s", entity_id)


def get_system_unique_id(entity: RegistryEntry):
    """Determine the system wide unique_id for an entity."""
    return f"{entity.platform}.{entity.domain}.{entity.unique_id}"


def get_plug_devices(hass, entity_configs):
    """Produce list of plug devices from config entities."""
    for entity_id, entity_config in entity_configs.items():
        state = hass.states.get(entity_id)
        if state is None:
            continue
        name = entity_config.get(CONF_NAME, state.name)

        if state.state == STATE_ON or state.domain == SENSOR_DOMAIN:
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
            elif state.domain == SENSOR_DOMAIN:
                power = float(state.state)
        else:
            power = 0.0
        last_changed = state.last_changed.timestamp()
        yield PlugInstance(
            entity_config[CONF_UNIQUE_ID],
            start_time=last_changed,
            alias=name,
            power=power,
        )
