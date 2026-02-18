"""Config flow for Proxmox VE integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from proxmoxer import AuthenticationError, ProxmoxAPI
from proxmoxer.core import ResourceException
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

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
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def _sanitize_userid(data: dict[str, Any]) -> str:
    """Sanitize the user ID."""
    return (
        data[CONF_USERNAME]
        if "@" in data[CONF_USERNAME]
        else f"{data[CONF_USERNAME]}@{data[CONF_REALM]}"
    )


def _get_nodes_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the user input and fetch data (sync, for executor)."""
    try:
        client = ProxmoxAPI(
            data[CONF_HOST],
            port=data[CONF_PORT],
            user=_sanitize_userid(data),
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

    nodes_data: list[dict[str, Any]] = []
    for node in nodes:
        try:
            vms = client.nodes(node["node"]).qemu.get()
            containers = client.nodes(node["node"]).lxc.get()
        except (ResourceException, requests.exceptions.ConnectionError) as err:
            raise ProxmoxNoNodesFound from err

        nodes_data.append(
            {
                CONF_NODE: node["node"],
                CONF_VMS: [vm["vmid"] for vm in vms],
                CONF_CONTAINERS: [container["vmid"] for container in containers],
            }
        )

    _LOGGER.debug("Nodes with data: %s", nodes_data)
    return nodes_data


class ProxmoxveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Proxmox VE."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        proxmox_nodes: list[dict[str, Any]] = []
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            proxmox_nodes, errors = await self._validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data={**user_input, CONF_NODES: proxmox_nodes},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth when Proxmox VE authentication fails."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth: ask for new password and validate."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            user_input = {**reauth_entry.data, **user_input}
            _, errors = await self._validate_input(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconf_entry = self._get_reconfigure_entry()
        suggested_values = {
            CONF_HOST: reconf_entry.data[CONF_HOST],
            CONF_PORT: reconf_entry.data[CONF_PORT],
            CONF_REALM: reconf_entry.data[CONF_REALM],
            CONF_USERNAME: reconf_entry.data[CONF_USERNAME],
            CONF_PASSWORD: reconf_entry.data[CONF_PASSWORD],
            CONF_VERIFY_SSL: reconf_entry.data[CONF_VERIFY_SSL],
        }

        if user_input:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            user_input = {**reconf_entry.data, **user_input}
            _, errors = await self._validate_input(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reconf_entry,
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_REALM: user_input[CONF_REALM],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=CONFIG_SCHEMA,
                suggested_values=user_input or suggested_values,
            ),
            errors=errors,
        )

    async def _validate_input(
        self, user_input: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Validate the user input. Return nodes data and/or errors."""
        errors: dict[str, str] = {}
        proxmox_nodes: list[dict[str, Any]] = []
        try:
            proxmox_nodes = await self.hass.async_add_executor_job(
                _get_nodes_data, user_input
            )
        except ProxmoxConnectTimeout:
            errors["base"] = "connect_timeout"
        except ProxmoxAuthenticationError:
            errors["base"] = "invalid_auth"
        except ProxmoxSSLError:
            errors["base"] = "ssl_error"
        except ProxmoxNoNodesFound:
            errors["base"] = "no_nodes_found"
        return proxmox_nodes, errors

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow initiated by configuration file."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})

        try:
            proxmox_nodes = await self.hass.async_add_executor_job(
                _get_nodes_data, import_data
            )
        except ProxmoxConnectTimeout:
            return self.async_abort(reason="connect_timeout")
        except ProxmoxAuthenticationError:
            return self.async_abort(reason="invalid_auth")
        except ProxmoxSSLError:
            return self.async_abort(reason="ssl_error")
        except ProxmoxNoNodesFound:
            return self.async_abort(reason="no_nodes_found")

        return self.async_create_entry(
            title=import_data[CONF_HOST],
            data={**import_data, CONF_NODES: proxmox_nodes},
        )


class ProxmoxNoNodesFound(HomeAssistantError):
    """Error to indicate no nodes found."""


class ProxmoxConnectTimeout(HomeAssistantError):
    """Error to indicate a connection timeout."""


class ProxmoxSSLError(HomeAssistantError):
    """Error to indicate an SSL error."""


class ProxmoxAuthenticationError(HomeAssistantError):
    """Error to indicate an authentication error."""
