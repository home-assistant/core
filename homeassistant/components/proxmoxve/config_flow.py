"""Config flow for Proxmox VE integration."""

from __future__ import annotations

import logging
from typing import Any

from proxmoxer import AuthenticationError, ProxmoxAPI
import requests
from requests.exceptions import ConnectTimeout, SSLError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .common import ResourceException
from .const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=8006): cv.port,
        vol.Optional(CONF_REALM, default=DEFAULT_REALM): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input and fetch data."""

    def create_proxmox_client():
        """Create a ProxmoxAPI client."""
        user_id = (
            data[CONF_USERNAME]
            if "@" in data[CONF_USERNAME]
            else f"{data[CONF_USERNAME]}@{data[CONF_REALM]}"
        )

        return ProxmoxAPI(
            data[CONF_HOST],
            port=data[CONF_PORT],
            user=user_id,
            password=data[CONF_PASSWORD],
            verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )

    try:
        client = await hass.async_add_executor_job(create_proxmox_client)
    except AuthenticationError as err:
        raise CannotConnect from err
    except SSLError as err:
        raise CannotConnect from err
    except ConnectTimeout as err:
        raise TimeoutError from err

    try:
        nodes = await hass.async_add_executor_job(client.nodes.get)
    except (ResourceException, requests.exceptions.ConnectionError) as err:
        raise NoNodesFound from err

    if not nodes:
        raise NoNodesFound

    _LOGGER.debug("Proxmox nodes: %s", nodes)

    nodes_data: list[dict[str, Any]] = []
    for node in nodes:
        try:
            vms = await hass.async_add_executor_job(client.nodes(node["node"]).qemu.get)
            containers = await hass.async_add_executor_job(
                client.nodes(node["node"]).lxc.get
            )
        except (ResourceException, requests.exceptions.ConnectionError) as err:
            raise NoNodesFound from err

        nodes_data.append(
            {
                "node": node["node"],
                "vms": vms,
                "containers": containers,
            }
        )

    _LOGGER.debug("Nodes with data: %s", nodes_data)
    return {"nodes": nodes_data}


class ProxmoxveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Proxmox VE."""

    VERSION = 1
    _proxmox_setup: dict[str, Any] | None = None
    _user_input: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._proxmox_setup = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except SSLError:
                errors["base"] = "ssl_error"
            except NoNodesFound:
                errors["base"] = "no_nodes_found"

            if "base" not in errors:
                self._user_input = user_input
                return await self.async_step_setup()

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )

    async def async_step_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the setup step."""
        assert self._proxmox_setup

        if user_input is not None:
            selected_nodes: list[dict[str, Any]] = []
            for node in self._proxmox_setup["nodes"]:
                if node["node"] in user_input[CONF_NODES]:
                    updated_node = {
                        CONF_NODE: node["node"],
                        CONF_VMS: [vm["vmid"] for vm in node["vms"]],
                        CONF_CONTAINERS: [
                            container["vmid"] for container in node["containers"]
                        ],
                    }
                    selected_nodes.append(updated_node)

            user_input[CONF_NODES] = selected_nodes
            assert self._user_input
            self._user_input |= user_input

            await self.async_set_unique_id(self._user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._user_input[CONF_HOST], data=self._user_input
            )

        return self.async_show_form(
            step_id="setup",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NODES): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                node["node"] for node in self._proxmox_setup["nodes"]
                            ],
                            mode=SelectSelectorMode.LIST,
                            multiple=True,
                        )
                    )
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class NoNodesFound(HomeAssistantError):
    """Error to indicate no nodes were found."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
