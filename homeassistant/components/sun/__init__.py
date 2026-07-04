"""Support for functionality to keep track of the sun."""

import logging

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

# The sensor platform is pre-imported here to ensure
# it gets loaded when the base component is loaded
# as we will always load it and we do not want to have
# to wait for the import executor when its busy later
# in the startup process.
from . import (
    binary_sensor as binary_sensor_pre_import,  # noqa: F401
    sensor as sensor_pre_import,  # noqa: F401
)
from .const import (  # noqa: F401  # noqa: F401
    DATA_COMPONENT,
    DOMAIN,
    STATE_ABOVE_HORIZON,
    STATE_BELOW_HORIZON,
)
from .entity import Sun, SunConfigEntry
from .services import async_setup_services

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track the state of the sun."""
    hass.data[DATA_COMPONENT] = EntityComponent[Sun](_LOGGER, DOMAIN, hass)
    async_setup_services(hass)
    if not hass.config_entries.async_entries(DOMAIN):
        # We avoid creating an import flow if its already
        # setup since it will have to import the config_flow
        # module.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config,
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SunConfigEntry) -> bool:
    """Set up from a config entry."""
    # Remove deprecated solar_rising sensor entity (removed in 2026.1)
    ent_reg = er.async_get(hass)
    if entity_id := ent_reg.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{entry.entry_id}-solar_rising"
    ):
        ent_reg.async_remove(entity_id)

    sun = Sun(hass)
    await hass.data[DATA_COMPONENT].async_add_entities([sun])
    entry.runtime_data = sun
    entry.async_on_unload(sun.remove_listeners)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SunConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_remove()
    return unload_ok
