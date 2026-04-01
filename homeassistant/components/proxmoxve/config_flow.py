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

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .common import sanitize_config_entry
from .const import (
    AUTH_METHODS,
    AUTH_OTHER,
    CONF_AUTH_METHOD,
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_TOKEN,
    CONF_TOKEN_ID,
    CONF_TOKEN_SECRET,
    CONF_VMS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTH_METHOD, default=DEFAULT_REALM): SelectSelector(
            SelectSelectorConfig(
                options=AUTH_METHODS,
                translation_key=CONF_AUTH_METHOD,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_TOKEN, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
    }
)
TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN_ID): cv.string,
        vol.Required(CONF_TOKEN_SECRET): cv.string,
    }
)


def _get_nodes_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the user input and fetch data (sync, for executor)."""
    auth_kwargs = {
        "password": data.get(CONF_PASSWORD),
    }
    if data.get(CONF_TOKEN):
        auth_kwargs = {
            "token_name": data[CONF_TOKEN_ID],
            "token_value": data[CONF_TOKEN_SECRET],
        }
    data = sanitize_config_entry(data)
    try:
        client = ProxmoxAPI(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            user=data[CONF_USERNAME],
            verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            **auth_kwargs,
        )
        nodes = client.nodes.get()
    except AuthenticationError as err:
        raise ProxmoxAuthenticationError from err
    except SSLError as err:
        raise ProxmoxSSLError from err
    except ConnectTimeout as err:
        raise ProxmoxConnectTimeout from err
    except ResourceException as err:
        raise ProxmoxNoNodesFound from err
    except requests.exceptions.ConnectionError as err:
        raise ProxmoxConnectionError from err

    nodes_data: list[dict[str, Any]] = []
    for node in nodes:
        try:
            vms = client.nodes(node["node"]).qemu.get()
            containers = client.nodes(node["node"]).lxc.get()
        except ResourceException as err:
            raise ProxmoxNoNodesFound from err
        except requests.exceptions.ConnectionError as err:
            raise ProxmoxConnectionError from err

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

    VERSION = 3
    _data: dict[str, Any] = {}
    _entry: ConfigEntry

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._data = user_input
            return await self.async_step_user_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=BASE_SCHEMA,
        )

    async def async_step_user_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the auth step."""
        errors: dict[str, str] = {}
        proxmox_nodes: list[dict[str, Any]] = []

        if user_input is not None:
            self._data = sanitize_config_entry({**self._data, **user_input})
            self._async_abort_entries_match({CONF_HOST: self._data[CONF_HOST]})
            proxmox_nodes, errors = await self._validate_input(self._data)

            if not errors:
                return self.async_create_entry(
                    title=self._data[CONF_HOST],
                    data={**self._data, CONF_NODES: proxmox_nodes},
                )

        return self.async_show_form(
            step_id="user_auth",
            data_schema=self._get_auth_schema(self._data),
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
        """Handle reauth: ask for updated credentials and validate."""
        errors: dict[str, str] = {}
        self._entry = self._get_reauth_entry()
        if user_input is not None:
            merged_data = {**self._entry.data, **user_input}
            _, errors = await self._validate_input(merged_data)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._entry,
                    data_updates=self._get_auth_updates(merged_data),
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._get_auth_schema(self._entry.data),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial reconfiguration step."""
        self._entry = self._get_reconfigure_entry()
        suggested_values = {
            CONF_AUTH_METHOD: self._entry.data.get(
                CONF_AUTH_METHOD, self._entry.data.get(CONF_REALM, DEFAULT_REALM)
            ),
            CONF_HOST: self._entry.data[CONF_HOST],
            CONF_USERNAME: self._entry.data[CONF_USERNAME].split("@")[0],
            CONF_PORT: self._entry.data[CONF_PORT],
            CONF_VERIFY_SSL: self._entry.data[CONF_VERIFY_SSL],
            CONF_TOKEN: self._entry.data.get(CONF_TOKEN, False),
            CONF_TOKEN_ID: self._entry.data.get(CONF_TOKEN_ID),
            CONF_REALM: self._entry.data[CONF_REALM],
        }
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            self._data = sanitize_config_entry({**self._entry.data, **user_input})
            return await self.async_step_reconfigure_auth()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=BASE_SCHEMA,
                suggested_values=self._data or suggested_values,
            ),
        )

    async def async_step_reconfigure_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: self._data[CONF_HOST]})
            self._data = sanitize_config_entry({**self._data, **user_input})
            _, errors = await self._validate_input(self._data)
            # Discard password/token from data to avoid storing
            data_kwargs = {
                CONF_PASSWORD: self._data.get(CONF_PASSWORD),
                CONF_TOKEN_ID: None,
                CONF_TOKEN_SECRET: None,
            }
            if self._data[CONF_TOKEN]:
                data_kwargs = {
                    CONF_TOKEN_ID: self._data[CONF_TOKEN_ID],
                    CONF_TOKEN_SECRET: self._data[CONF_TOKEN_SECRET],
                    CONF_PASSWORD: None,
                }
            if not errors:
                return self.async_update_reload_and_abort(
                    self._entry,
                    data_updates={
                        CONF_AUTH_METHOD: self._data[CONF_AUTH_METHOD],
                        CONF_HOST: self._data[CONF_HOST],
                        CONF_USERNAME: self._data[CONF_USERNAME],
                        CONF_PORT: self._data[CONF_PORT],
                        CONF_VERIFY_SSL: self._data[CONF_VERIFY_SSL],
                        CONF_TOKEN: self._data[CONF_TOKEN],
                        CONF_REALM: self._data[CONF_REALM],
                        **data_kwargs,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure_auth",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=self._get_auth_schema(self._data),
                suggested_values=sanitize_config_entry(self._data),
            ),
            errors=errors,
        )

    async def _validate_input(
        self, user_input: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Validate the user input. Return nodes data and/or errors."""
        errors: dict[str, str] = {}
        proxmox_nodes: list[dict[str, Any]] = []
        err: ProxmoxError | None = None
        try:
            proxmox_nodes = await self.hass.async_add_executor_job(
                _get_nodes_data, user_input
            )
        except ProxmoxConnectTimeout as exc:
            errors["base"] = "connect_timeout"
            err = exc
        except ProxmoxAuthenticationError as exc:
            errors["base"] = "invalid_auth"
            err = exc
        except ProxmoxSSLError as exc:
            errors["base"] = "ssl_error"
            err = exc
        except ProxmoxNoNodesFound as exc:
            errors["base"] = "no_nodes_found"
            err = exc
        except ProxmoxConnectionError as exc:
            errors["base"] = "cannot_connect"
            err = exc

        if err is not None:
            _LOGGER.debug("Error: %s: %s", errors["base"], err)

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
        except ProxmoxConnectionError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=import_data[CONF_HOST],
            data={**import_data, CONF_NODES: proxmox_nodes},
        )

    def _get_auth_schema(
        self,
        data: Mapping[str, Any],
    ) -> vol.Schema:
        """Return the auth schema based on the flow data."""
        schema = PASSWORD_SCHEMA
        if data.get(CONF_TOKEN):
            schema = TOKEN_SCHEMA
        if data.get(CONF_AUTH_METHOD) == AUTH_OTHER:
            schema = schema.extend({vol.Required(CONF_REALM): cv.string})
        return schema

    def _get_auth_updates(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the auth updates based on the flow data."""
        updates = {CONF_PASSWORD: data.get(CONF_PASSWORD)}
        if data.get(CONF_TOKEN):
            updates = {
                CONF_TOKEN_ID: data[CONF_TOKEN_ID],
                CONF_TOKEN_SECRET: data[CONF_TOKEN_SECRET],
            }
        if data.get(CONF_AUTH_METHOD) == AUTH_OTHER:
            updates[CONF_REALM] = data.get(CONF_REALM, DEFAULT_REALM)
        return updates


class ProxmoxError(HomeAssistantError):
    """Base class for Proxmox VE errors."""


class ProxmoxNoNodesFound(ProxmoxError):
    """Error to indicate no nodes found."""


class ProxmoxConnectTimeout(ProxmoxError):
    """Error to indicate a connection timeout."""


class ProxmoxSSLError(ProxmoxError):
    """Error to indicate an SSL error."""


class ProxmoxAuthenticationError(ProxmoxError):
    """Error to indicate an authentication error."""


class ProxmoxConnectionError(ProxmoxError):
    """Error to indicate a connection error."""
