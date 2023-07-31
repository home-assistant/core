"""Support for Supla devices."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from asyncpysupla import SuplaAPI
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN = "supla"
CONF_SERVER = "server"
CONF_SERVERS = "servers"

SCAN_INTERVAL = timedelta(seconds=10)

SUPLA_FUNCTION_HA_CMP_MAP = {
    "CONTROLLINGTHEROLLERSHUTTER": Platform.COVER,
    "CONTROLLINGTHEGATE": Platform.COVER,
    "CONTROLLINGTHEGARAGEDOOR": Platform.COVER,
    "LIGHTSWITCH": Platform.SWITCH,
}
SUPLA_FUNCTION_NONE = "NONE"
SUPLA_SERVERS = "supla_servers"
SUPLA_COORDINATORS = "supla_coordinators"

SERVER_CONFIG = vol.Schema(
    {
        vol.Required(CONF_SERVER): cv.string,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [SERVER_CONFIG])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up the Supla component."""

    server_confs = base_config[DOMAIN][CONF_SERVERS]

    hass.data[DOMAIN] = {SUPLA_SERVERS: {}, SUPLA_COORDINATORS: {}}

    session = async_get_clientsession(hass)

    for server_conf in server_confs:
        server_address = server_conf[CONF_SERVER]

        server = SuplaAPI(server_address, server_conf[CONF_ACCESS_TOKEN], session)

        # Test connection
        try:
            srv_info = await server.get_server_info()
            if srv_info.get("authenticated"):
                hass.data[DOMAIN][SUPLA_SERVERS][server_conf[CONF_SERVER]] = server

            else:
                _LOGGER.error(
                    "Server: %s not configured. API call returned: %s",
                    server_address,
                    srv_info,
                )
                return False
        except OSError:
            _LOGGER.exception(
                "Server: %s not configured. Error on Supla API access: ", server_address
            )
            return False

    await discover_devices(hass, base_config)

    return True


async def discover_devices(hass, hass_config):
    """Run periodically to discover new devices.

    Currently it is only run at startup.
    """
    component_configs: dict[Platform, dict[str, dict]] = {}

    for server_name, server in hass.data[DOMAIN][SUPLA_SERVERS].items():

        async def _fetch_channels():
            async with async_timeout.timeout(SCAN_INTERVAL.total_seconds()):
                channels = {
                    channel["id"]: channel
                    # pylint: disable-next=cell-var-from-loop
                    for channel in await server.get_channels(  # noqa: B023
                        include=["iodevice", "state", "connected"]
                    )
                }
                return channels

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{server_name}",
            update_method=_fetch_channels,
            update_interval=SCAN_INTERVAL,
        )

        await coordinator.async_refresh()

        hass.data[DOMAIN][SUPLA_COORDINATORS][server_name] = coordinator

        for channel_id, channel in coordinator.data.items():
            channel_function = channel["function"]["name"]

            if channel_function == SUPLA_FUNCTION_NONE:
                _LOGGER.debug(
                    "Ignored function: %s, channel ID: %s",
                    channel_function,
                    channel["id"],
                )
                continue

            component_name = SUPLA_FUNCTION_HA_CMP_MAP.get(channel_function)

            if component_name is None:
                _LOGGER.warning(
                    "Unsupported function: %s, channel ID: %s",
                    channel_function,
                    channel["id"],
                )
                continue

            channel["server_name"] = server_name
            component_config = component_configs.setdefault(component_name, {})
            component_config[f"{server_name}_{channel_id}"] = {
                "channel_id": channel_id,
                "server_name": server_name,
                "function_name": channel["function"]["name"],
            }

    # Load discovered devices
    for component_name, config in component_configs.items():
        await async_load_platform(hass, component_name, DOMAIN, config, hass_config)
