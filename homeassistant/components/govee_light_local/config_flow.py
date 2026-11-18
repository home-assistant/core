"""Config flow for Govee light local."""

import asyncio
from contextlib import suppress
import ipaddress
import logging
from typing import Any, override

from govee_local_api import GoveeController
import probatio

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from . import async_get_listening_addresses
from .const import (
    CONF_HOSTS,
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)
from .coordinator import GoveeLocalConfigEntry, log_bound_addresses

_LOGGER = logging.getLogger(__name__)

HOSTS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_HOSTS, default=[]): TextSelector(
            TextSelectorConfig(multiple=True)
        )
    }
)


def _parse_hosts(raw: list[str]) -> list[str] | None:
    """Normalize the entered addresses; None if any is not a valid IPv4 address."""

    hosts: list[str] = []
    for value in raw:
        if not (value := value.strip()):
            continue
        try:
            host = str(ipaddress.IPv4Address(value))
        except ValueError:
            return None
        if host not in hosts:
            hosts.append(host)
    return hosts


async def _async_has_devices(hass: HomeAssistant, hosts: list[str]) -> bool:
    """Return if there are devices that can be discovered."""

    listening_addresses = await async_get_listening_addresses(hass)
    if not listening_addresses:
        _LOGGER.debug("No enabled IPv4 addresses to listen on")
        return False

    controller: GoveeController = GoveeController(
        loop=hass.loop,
        logger=_LOGGER,
        listening_addresses=listening_addresses,
        broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
        broadcast_port=CONF_TARGET_PORT_DEFAULT,
        listening_port=CONF_LISTENING_PORT_DEFAULT,
        discovery_enabled=True,
        discovery_interval=1,
        update_enabled=False,
    )
    # Probe devices multicast cannot reach, such as lights on another VLAN.
    for host in hosts:
        controller.add_device_to_discovery_queue(host)

    try:
        _LOGGER.debug(
            "Starting discovery on %s, probing %s", listening_addresses, hosts
        )
        # Probe through whichever adapters bind; only a total failure aborts.
        await controller.start(require_all=False)
    except OSError as ex:
        _LOGGER.error("Start failed, errno: %d", ex.errno)
        return False

    log_bound_addresses(controller)

    try:
        async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
            while not controller.devices:
                await asyncio.sleep(delay=1)
    except TimeoutError:
        _LOGGER.debug("No devices found")

    devices_count = len(controller.devices)
    cleanup_complete: asyncio.Event = controller.cleanup()
    with suppress(TimeoutError):
        await asyncio.wait_for(cleanup_complete.wait(), 1)

    return devices_count > 0


class GoveeLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee light local."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Discover devices, also probing any addresses entered."""

        errors: dict[str, str] = {}
        if user_input is not None:
            hosts = _parse_hosts(user_input[CONF_HOSTS])
            if hosts is None:
                errors[CONF_HOSTS] = "invalid_host"
            elif await _async_has_devices(self.hass, hosts):
                return self.async_create_entry(
                    title="Govee light local", data={}, options={CONF_HOSTS: hosts}
                )
            else:
                errors["base"] = "no_devices_found"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(HOSTS_SCHEMA, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: GoveeLocalConfigEntry,
    ) -> GoveeLocalOptionsFlow:
        """Get the options flow for this handler."""
        return GoveeLocalOptionsFlow()


class GoveeLocalOptionsFlow(OptionsFlowWithReload):
    """Edit the addresses that are probed by unicast."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the device addresses."""

        errors: dict[str, str] = {}
        if user_input is not None:
            hosts = _parse_hosts(user_input[CONF_HOSTS])
            if hosts is None:
                errors[CONF_HOSTS] = "invalid_host"
            else:
                return self.async_create_entry(data={CONF_HOSTS: hosts})

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                HOSTS_SCHEMA, user_input or self.config_entry.options
            ),
            errors=errors,
        )
