"""Config flow for Roth Touchline integration."""

import asyncio
import logging
from typing import Any, override

import probatio
from pytouchline_extended import (
    DiscoveredController,
    TouchlineController,
    TouchlineError,
    discover_controllers,
)
from yarl import URL

from homeassistant.components import network
from homeassistant.config_entries import SOURCE_IGNORE, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.util.network import is_ip_address

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


MANUAL_ENTRY = "manual"

STEP_MANUAL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): cv.string,
    }
)


async def _async_validate_input(data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect, and return the controller ID."""
    host = data[CONF_HOST]

    try:
        state = await TouchlineController(url=host).fetch_async()
    except TouchlineError as err:
        _LOGGER.debug(
            "Error while connecting to Touchline controller at %s", host, exc_info=True
        )
        raise CannotConnect from err

    # The ID that the thermostats report as their owner identifies the controller.
    if not state.rooms or (controller_id := state.rooms[0].controller_id) is None:
        raise CannotConnect
    return str(controller_id)


async def _async_search_network(broadcast_address: str) -> list[DiscoveredController]:
    """Search one network for controllers."""
    try:
        return await discover_controllers(broadcast_address=broadcast_address)
    except TouchlineError as err:
        _LOGGER.debug("Searching %s for controllers failed: %s", broadcast_address, err)
        return []


async def _async_discover_controllers(
    hass: HomeAssistant,
) -> list[DiscoveredController]:
    """Search every IPv4 network that Home Assistant is on for controllers."""
    results = await asyncio.gather(
        *(
            _async_search_network(str(address))
            for address in await network.async_get_ipv4_broadcast_addresses(hass)
        )
    )
    # The global and the subnet broadcast reach the same controllers.
    controllers = {
        controller.controller_id: controller
        for result in results
        for controller in result
    }
    return list(controllers.values())


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class TouchlineConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roth Touchline."""

    VERSION = 1

    _discovered_host: str
    _discovered_controllers: dict[str, DiscoveredController]

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a controller found on the network, or enter one."""
        if user_input is not None:
            if user_input[CONF_DEVICE] == MANUAL_ENTRY:
                return await self.async_step_manual()

            host = self._discovered_controllers[user_input[CONF_DEVICE]].url
            try:
                unique_id = await _async_validate_input({CONF_HOST: host})
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

            await self.async_set_unique_id(unique_id, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=host, data={CONF_HOST: host})

        controllers = await _async_discover_controllers(self.hass)
        current_ids = self._async_current_ids(include_ignore=False)
        current_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }
        self._discovered_controllers = {
            str(controller.controller_id): controller
            for controller in controllers
            if str(controller.controller_id) not in current_ids
            and controller.url not in current_hosts
        }
        if not self._discovered_controllers:
            return await self.async_step_manual()

        options = [
            SelectOptionDict(
                value=controller_id,
                label=f"{controller.url} ({controller.mac_address})",
            )
            for controller_id, controller in self._discovered_controllers.items()
        ]
        options.append(SelectOptionDict(value=MANUAL_ENTRY, label=MANUAL_ENTRY))
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            translation_key=CONF_DEVICE,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a controller URL entered by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                unique_id = await _async_validate_input(user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a controller discovered via DHCP."""
        host = f"http://{discovery_info.ip}"
        self._async_abort_entries_match({CONF_HOST: host})

        try:
            unique_id = await _async_validate_input({CONF_HOST: host})
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        existing_entry = await self.async_set_unique_id(unique_id)
        updates = None
        # A hostname the user entered is kept; only an IP address is replaced.
        if (
            existing_entry is not None
            and existing_entry.source != SOURCE_IGNORE
            and (stored_host := URL(existing_entry.data[CONF_HOST]).host) is not None
            and is_ip_address(stored_host)
        ):
            updates = {CONF_HOST: host}
        self._abort_if_unique_id_configured(updates=updates)

        self._discovered_host = host
        self.context["title_placeholders"] = {"host": host}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setting up a discovered controller."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_host, data={CONF_HOST: self._discovered_host}
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": self._discovered_host},
        )
