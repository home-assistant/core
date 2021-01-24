"""Support for botvac connected Vorwerk vacuum cleaners."""
import asyncio
import logging

from pybotvac.exceptions import NeatoException
from pybotvac.robot import Robot
from pybotvac.vorwerk import Vorwerk
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    VORWERK_DOMAIN,
    VORWERK_PLATFORMS,
    VORWERK_ROBOT_ENDPOINT,
    VORWERK_ROBOT_NAME,
    VORWERK_ROBOT_SECRET,
    VORWERK_ROBOT_SERIAL,
    VORWERK_ROBOT_TRAITS,
    VORWERK_ROBOTS,
)

_LOGGER = logging.getLogger(__name__)


VORWERK_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(VORWERK_ROBOT_NAME): cv.string,
            vol.Required(VORWERK_ROBOT_SERIAL): cv.string,
            vol.Required(VORWERK_ROBOT_SECRET): cv.string,
            vol.Optional(
                VORWERK_ROBOT_ENDPOINT, default="https://nucleo.ksecosys.com:4443"
            ): cv.string,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    {VORWERK_DOMAIN: vol.Schema(vol.All(cv.ensure_list, [VORWERK_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Vorwerk component."""
    hass.data[VORWERK_DOMAIN] = {}

    if VORWERK_DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                VORWERK_DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[VORWERK_DOMAIN],
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    def create_robot(config):
        return Robot(
            serial=config[VORWERK_ROBOT_SERIAL],
            secret=config[VORWERK_ROBOT_SECRET],
            traits=config.get(VORWERK_ROBOT_TRAITS, []),
            vendor=Vorwerk(),
            name=config[VORWERK_ROBOT_NAME],
            endpoint=config[VORWERK_ROBOT_ENDPOINT],
        )

    try:
        robots = await asyncio.gather(
            *(
                hass.async_add_executor_job(create_robot, robot_conf)
                for robot_conf in entry.data[VORWERK_ROBOTS]
            ),
            return_exceptions=False,
        )
        hass.data[VORWERK_DOMAIN][entry.entry_id] = {VORWERK_ROBOTS: robots}
    except NeatoException as ex:
        _LOGGER.warning(
            "Failed to connect to robot %s: %s", entry.data[VORWERK_ROBOT_NAME], ex
        )
        raise ConfigEntryNotReady from ex

    for component in VORWERK_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_ok: bool = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in VORWERK_PLATFORMS
            )
        )
    )
    if unload_ok:
        hass.data[VORWERK_DOMAIN].pop(entry.entry_id)
    return unload_ok
