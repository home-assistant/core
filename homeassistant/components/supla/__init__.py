"""Support for Supla devices."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from asyncpysupla import SuplaAPI
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "supla"
CONF_SERVER = "server"
CONF_SERVERS = "servers"

SCAN_INTERVAL = timedelta(seconds=10)

SUPLA_FUNCTION_HA_CMP_MAP = {
    "CONTROLLINGTHEROLLERSHUTTER": "cover",
    "CONTROLLINGTHEGATE": "cover",
    "LIGHTSWITCH": "switch",
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


async def async_setup(hass, base_config):
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
    """
    Run periodically to discover new devices.

    Currently it is only run at startup.
    """
    component_configs = {}

    for server_name, server in hass.data[DOMAIN][SUPLA_SERVERS].items():

        async def _fetch_channels():
            async with async_timeout.timeout(SCAN_INTERVAL.total_seconds()):
                channels = {
                    channel["id"]: channel
                    for channel in await server.get_channels(
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
            component_configs.setdefault(component_name, []).append(
                {
                    "channel_id": channel_id,
                    "server_name": server_name,
                    "function_name": channel["function"]["name"],
                }
            )

    # Load discovered devices
    for component_name, config in component_configs.items():
        await async_load_platform(hass, component_name, DOMAIN, config, hass_config)


class SuplaChannel(CoordinatorEntity):
    """Base class of a Supla Channel (an equivalent of HA's Entity)."""

    def __init__(self, config, server, coordinator):
        """Init from config, hookup[ server and coordinator."""
        super().__init__(coordinator)
        self.server_name = config["server_name"]
        self.channel_id = config["channel_id"]
        self.server = server

    @property
    def channel_data(self):
        """Return channel data taken from coordinator."""
        return self.coordinator.data.get(self.channel_id)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "supla-{}-{}".format(
            self.channel_data["iodevice"]["gUIDString"].lower(),
            self.channel_data["channelNumber"],
        )

    @property
    def name(self) -> str | None:
        """Return the name of the device."""
        return self.channel_data["caption"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.channel_data is None:
            return False
        state = self.channel_data.get("state")
        if state is None:
            return False
        return state.get("connected")

    async def async_action(self, action, **add_pars):
        """
        Run server action.

        Actions are currently hardcoded in components.
        Supla's API enables autodiscovery
        """
        _LOGGER.debug(
            "Executing action %s on channel %d, params: %s",
            action,
            self.channel_data["id"],
            add_pars,
        )
        await self.server.execute_action(self.channel_data["id"], action, **add_pars)

        # Update state
        await self.coordinator.async_request_refresh()
