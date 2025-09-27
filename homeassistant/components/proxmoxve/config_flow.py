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
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
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
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_REALM, default=DEFAULT_REALM): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
    }
)


def _validate_input_sync(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the user input and fetch data (sync, for executor)."""
    user_id = (
        data[CONF_USERNAME]
        if "@" in data[CONF_USERNAME]
        else f"{data[CONF_USERNAME]}@{data[CONF_REALM]}"
    )

    try:
        client = ProxmoxAPI(
            data[CONF_HOST],
            port=data[CONF_PORT],
            user=user_id,
            password=data[CONF_PASSWORD],
            verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
        nodes = client.nodes.get()
    except AuthenticationError as err:
        raise ProxmoxAuthenticationError from err
    except SSLError as err:
        raise ProxmoxSSLError from err
    except ConnectTimeout as err:
        raise ProxmoxConnectTimeout from err
    except (ResourceException, requests.exceptions.ConnectionError) as err:
        raise ProxmoxNoNodesFound from err

    _LOGGER.debug("Proxmox nodes: %s", nodes)

    nodes_data: list[dict[str, Any]] = []
    for node in nodes:
        try:
            vms = client.nodes(node["node"]).qemu.get()
            containers = client.nodes(node["node"]).lxc.get()
        except (ResourceException, requests.exceptions.ConnectionError) as err:
            raise ProxmoxNoNodesFound from err

        nodes_data.append(
            {
                "node": node["node"],
                "vms": vms,
                "containers": containers,
            }
        )

    _LOGGER.debug("Nodes with data: %s", nodes_data)
    return nodes_data


async def _validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return a simple wrapper to validate the user input."""
    return await hass.async_add_executor_job(_validate_input_sync, data)


class ProxmoxveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Proxmox VE."""

    VERSION = 1
    _proxmox_nodes: list[dict[str, Any]] = []
    _user_input: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._proxmox_nodes = await _validate_input(self.hass, user_input)
            except ProxmoxConnectTimeout:
                errors["base"] = "connect_timeout"
            except ProxmoxAuthenticationError:
                errors["base"] = "invalid_auth"
            except ProxmoxSSLError:
                errors["base"] = "ssl_error"
            except ProxmoxNoNodesFound:
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
        if user_input is None:
            return self.async_show_form(
                step_id="setup",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NODES): SelectSelector(
                            SelectSelectorConfig(
                                options=[node["node"] for node in self._proxmox_nodes],
                                mode=SelectSelectorMode.LIST,
                                multiple=True,
                            )
                        )
                    }
                ),
            )

        selected_nodes: list[dict[str, Any]] = []
        for node in self._proxmox_nodes:
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
        self._user_input |= user_input

        await self.async_set_unique_id(self._user_input[CONF_HOST])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._user_input[CONF_HOST], data=self._user_input
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by configuration file."""
        async_create_issue(
            self.hass,
            DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2025.11.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Proxmox VE",
            },
        )

        return await self.async_step_user(user_input)


class ProxmoxNoNodesFound(HomeAssistantError):
    """Error to indicate no nodes found."""


class ProxmoxConnectTimeout(HomeAssistantError):
    """Error to indicate a connection timeout."""


class ProxmoxSSLError(HomeAssistantError):
    """Error to indicate an SSL error."""


class ProxmoxAuthenticationError(HomeAssistantError):
    """Error to indicate an authentication error."""
