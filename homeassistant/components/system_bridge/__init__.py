"""The System Bridge integration."""
import asyncio
from datetime import timedelta
import logging
import shlex
from typing import Any, Dict, Optional

import async_timeout
from systembridge import Bridge
from systembridge.client import BridgeClient
from systembridge.exceptions import BridgeAuthenticationException
from systembridge.objects.command.response import CommandResponse
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_COMMAND, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import BRIDGE_CONNECTION_ERRORS, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CONF_ARGUMENTS = "arguments"
CONF_BRIDGE = "bridge"
CONF_WAIT = "wait"

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BRIDGE): cv.string,
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_ARGUMENTS, []): cv.string,
    }
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the System Bridge integration."""

    async def handle_send_command(call):
        """Handle the service call."""
        device_registry = await hass.helpers.device_registry.async_get_registry()
        device_entry = device_registry.async_get(call.data.get(CONF_BRIDGE))

        command = call.data.get(CONF_COMMAND)
        arguments = shlex.split(call.data.get(CONF_ARGUMENTS, ""))

        coordinator: DataUpdateCoordinator = hass.data[DOMAIN][
            next(iter(device_entry.config_entries))
        ]
        bridge: Bridge = coordinator.data

        _LOGGER.debug(
            "Command payload: %s",
            {CONF_COMMAND: command, CONF_ARGUMENTS: arguments, CONF_WAIT: False},
        )
        try:
            response: CommandResponse = await bridge.async_send_command(
                {CONF_COMMAND: command, CONF_ARGUMENTS: arguments, CONF_WAIT: False}
            )
            if response.success:
                _LOGGER.debug(
                    "Sent command. Response message was: %s", response.message
                )
            else:
                _LOGGER.warning(
                    "Error sending command. Response message was: %s", response.message
                )
        except (BridgeAuthenticationException, *BRIDGE_CONNECTION_ERRORS) as exception:
            _LOGGER.error("Error sending command. Error was: %s", exception)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        handle_send_command,
        schema=SERVICE_SEND_COMMAND_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up System Bridge from a config entry."""

    client = Bridge(
        BridgeClient(aiohttp_client.async_get_clientsession(hass)),
        f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
        entry.data[CONF_API_KEY],
    )

    async def async_update_data() -> Bridge:
        """Fetch data from Bridge."""
        try:
            async with async_timeout.timeout(10):
                await client.async_get_battery()
                await client.async_get_cpu()
                await client.async_get_filesystem()
                await client.async_get_network()
                await client.async_get_os()
                await client.async_get_processes()
                await client.async_get_system()
            return client
        except (BridgeAuthenticationException, *BRIDGE_CONNECTION_ERRORS) as exception:
            raise UpdateFailed(exception) from exception

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name=f"{DOMAIN}_coordinator",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=120),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class BridgeEntity(CoordinatorEntity):
    """Defines a base System Bridge entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bridge: Bridge,
        key: str,
        name: str,
        icon: Optional[str],
    ) -> None:
        """Initialize the System Bridge entity."""
        super().__init__(coordinator)
        self._key = f"{bridge.os.hostname}_{key}"
        self._name = f"{bridge.os.hostname} {name}"
        self._icon = icon
        self._hostname = bridge.os.hostname
        self._default_interface = bridge.network.interfaces[
            bridge.network.interfaceDefault
        ]
        self._manufacturer = bridge.system.system.manufacturer
        self._model = bridge.system.system.model
        self._version = bridge.system.system.version

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._key

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon


class BridgeDeviceEntity(BridgeEntity):
    """Defines a System Bridge device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this System Bridge instance."""
        return {
            "connections": {
                (dr.CONNECTION_NETWORK_MAC, self._default_interface["mac"])
            },
            "manufacturer": self._manufacturer,
            "model": self._model,
            "name": self._hostname,
            "sw_version": self._version,
        }
