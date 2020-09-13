"""The totalconnect component."""
import asyncio
import logging

from total_connect_client import TotalConnectClient

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_USERCODES, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["alarm_control_panel", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up by configuration file."""
    if DOMAIN not in config:
        return True

    config_data = {}
    config_data[CONF_USERNAME] = config[DOMAIN].get(CONF_USERNAME)
    config_data[CONF_PASSWORD] = config[DOMAIN].get(CONF_PASSWORD)

    if CONF_USERCODES in config[DOMAIN]:
        config_data[CONF_USERCODES] = dict(config[DOMAIN][CONF_USERCODES])
    else:
        config_data[CONF_USERCODES] = {}
        _LOGGER.error("TotalConnect configuration is missing usercodes")

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config_data,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up upon config entry in user interface."""
    hass.data.setdefault(DOMAIN, {})

    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    if CONF_USERCODES in conf:
        temp_codes = conf[CONF_USERCODES]
        usercodes = {}
        for code in temp_codes:
            usercodes[int(code)] = temp_codes[code]
    else:
        _LOGGER.warning("No usercodes in TotalConnect configuration")

    client = await hass.async_add_executor_job(
        TotalConnectClient.TotalConnectClient, username, password, usercodes
    )

    if not client.is_valid_credentials():
        _LOGGER.error("TotalConnect authentication failed")
        return False

    hass.data[DOMAIN][entry.entry_id] = client

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
