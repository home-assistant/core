"""Support for functionality to keep track of the sun."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

# The sensor platform is pre-imported here to ensure
# it gets loaded when the base component is loaded
# as we will always load it and we do not want to have
# to wait for the import executor when its busy later
# in the startup process.
from . import sensor as sensor_pre_import  # noqa: F401
from .const import (  # noqa: F401  # noqa: F401
    DOMAIN,
    STATE_ABOVE_HORIZON,
    STATE_BELOW_HORIZON,
)
from .entity import Sun

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track the state of the sun."""
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data[DOMAIN] = Sun(hass)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR]
    ):
        sun: Sun = hass.data.pop(DOMAIN)
        sun.remove_listeners()
        hass.states.async_remove(sun.entity_id)
    return unload_ok
