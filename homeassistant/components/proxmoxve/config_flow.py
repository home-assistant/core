"""Config Flow for ProxmoxVE."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import proxmoxer
from requests.exceptions import ConnectTimeout, SSLError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from . import ProxmoxClient
from .const import (
    CONF_CONTAINERS,
    CONF_LXC,
    CONF_NODE,
    CONF_NODES,
    CONF_QEMU,
    CONF_REALM,
    CONF_VMS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    ID,
)

_LOGGER = logging.getLogger(__name__)


class ProxmoxOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for ProxmoxVE."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize ProxmoxVE options flow."""
        self.config_entry = config_entry
        self._proxmox_client: ProxmoxClient
        self._nodes: dict[str, Any] = {}
        self._config: dict[str, Any] = {}
        self._host: str | None = None

    async def async_step_init(self, user_input: dict[str, Any]) -> FlowResult:
        """Manage the options."""
        return await self.async_step_host(user_input)

    async def async_step_host(self, user_input: dict[str, Any]) -> FlowResult:
        """Manage the host options step for proxmoxve config flow."""
        errors = {}

        if user_input is not None:
            host = self.config_entry.data[CONF_HOST]
            port = self.config_entry.data[CONF_PORT]
            user = user_input.get(CONF_USERNAME)
            realm = user_input.get(CONF_REALM)
            password = user_input.get(CONF_PASSWORD)
            verify_ssl = user_input.get(CONF_VERIFY_SSL)

            try:
                self._proxmox_client = ProxmoxClient(
                    host,
                    port=port,
                    user=user,
                    realm=realm,
                    password=password,
                    verify_ssl=verify_ssl,
                )

                await self.hass.async_add_executor_job(
                    self._proxmox_client.build_client
                )

            except proxmoxer.backends.https.AuthenticationError:
                errors[CONF_USERNAME] = "auth_error"
            except SSLError:
                errors[CONF_VERIFY_SSL] = "ssl_rejection"
            except ConnectTimeout:
                errors[CONF_HOST] = "cant_connect"
            except Exception:  # pylint: disable=broad-except
                errors[CONF_BASE] = "general_error"

            else:
                if CONF_HOST in self.config_entry.data:
                    user_input[CONF_HOST] = self.config_entry.data[CONF_HOST]
                if CONF_PORT in self.config_entry.data:
                    user_input[CONF_PORT] = self.config_entry.data[CONF_PORT]
                if CONF_NODE in self.config_entry.data:
                    user_input[CONF_NODE] = self.config_entry.data[CONF_NODE]
                if CONF_QEMU in self.config_entry.data:
                    user_input[CONF_QEMU] = self.config_entry.data[CONF_QEMU]
                if CONF_LXC in self.config_entry.data:
                    user_input[CONF_LXC] = self.config_entry.data[CONF_LXC]
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=user_input,
                    options=self.config_entry.options,
                )
                return await self.async_step_selection_qemu_lxc()

        if errors:
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Optional(
                        CONF_REALM, default=user_input.get(CONF_REALM, "")
                    ): str,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    ): bool,
                }
            )

            return self.async_show_form(
                step_id="host", data_schema=data_schema, errors=errors
            )

        return self.async_show_form(
            step_id="host",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=self.config_entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=self.config_entry.data.get(CONF_PASSWORD, ""),
                    ): str,
                    vol.Optional(
                        CONF_REALM,
                        default=self.config_entry.data.get(CONF_REALM, ""),
                    ): str,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=self.config_entry.data.get(
                            CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                        ),
                    ): bool,
                }
            ),
        )

    async def async_step_selection_qemu_lxc(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the QEMU/LXC selection step."""

        if user_input is None:

            old_qemu = []
            for qemu in self.config_entry.data[CONF_QEMU]:
                old_qemu.append(qemu)

            old_lxc = []
            for lxc in self.config_entry.data[CONF_LXC]:
                old_lxc.append(lxc)

            node = self.config_entry.data[CONF_NODE]
            proxmox = self._proxmox_client.get_api_client()

            qemu_list_for_multi_select: list[int] = [
                int(qemu[ID])
                for qemu in await self.hass.async_add_executor_job(
                    proxmox.nodes(node).qemu.get
                )
            ]
            lxc_list_for_multi_select: list[int] = [
                int(lxc[ID])
                for lxc in await self.hass.async_add_executor_job(
                    proxmox.nodes(node).lxc.get
                )
            ]

            return self.async_show_form(
                step_id="selection_qemu_lxc",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NODE): node,
                        vol.Optional(CONF_QEMU, default=old_qemu): cv.multi_select(
                            qemu_list_for_multi_select
                        ),
                        vol.Optional(CONF_LXC, default=old_lxc): cv.multi_select(
                            lxc_list_for_multi_select
                        ),
                    }
                ),
            )

        if CONF_QEMU not in self._config:
            self._config[CONF_QEMU] = []
        if (
            CONF_QEMU in user_input
            and (qemu_user := user_input.get(CONF_QEMU)) is not None
        ):
            for qemu_selection in qemu_user:
                self._config[CONF_QEMU].append(qemu_selection)

        if CONF_LXC not in self._config:
            self._config[CONF_LXC] = []
        if (
            CONF_LXC in user_input
            and (lxc_user := user_input.get(CONF_LXC)) is not None
        ):
            for lxc_selection in lxc_user:
                self._config[CONF_LXC].append(lxc_selection)

        user_input = {}
        if CONF_HOST in self.config_entry.data:
            self._config[CONF_HOST] = self.config_entry.data[CONF_HOST]
        if CONF_PORT in self.config_entry.data:
            self._config[CONF_PORT] = self.config_entry.data[CONF_PORT]
        if CONF_USERNAME in self.config_entry.data:
            self._config[CONF_USERNAME] = self.config_entry.data[CONF_USERNAME]
        if CONF_REALM in self.config_entry.data:
            self._config[CONF_REALM] = self.config_entry.data[CONF_REALM]
        if CONF_PASSWORD in self.config_entry.data:
            self._config[CONF_PASSWORD] = self.config_entry.data[CONF_PASSWORD]
        if CONF_VERIFY_SSL in self.config_entry.data:
            self._config[CONF_VERIFY_SSL] = self.config_entry.data[CONF_VERIFY_SSL]
        if CONF_NODE in self.config_entry.data:
            self._config[CONF_NODE] = self.config_entry.data[CONF_NODE]

        for qemu in self.config_entry.data[CONF_QEMU]:
            if qemu not in self._config[CONF_QEMU]:
                # Remove device
                host_port_node_vm = f"{self.config_entry.data[CONF_HOST]}_{self.config_entry.data[CONF_PORT]}_{self.config_entry.data[CONF_NODE]}_{qemu}"
                device_identifiers = {(DOMAIN, host_port_node_vm)}
                dev_reg = dr.async_get(self.hass)
                device = dev_reg.async_get_or_create(
                    config_entry_id=self.config_entry.entry_id,
                    identifiers=device_identifiers,
                )
                dev_reg.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )
                _LOGGER.debug("Device %s removed", device.name)

        for lxc in self.config_entry.data[CONF_LXC]:
            if lxc not in self._config[CONF_LXC]:
                # Remove device
                host_port_node_vm = f"{self.config_entry.data[CONF_HOST]}_{self.config_entry.data[CONF_PORT]}_{self.config_entry.data[CONF_NODE]}_{lxc}"
                device_identifiers = {(DOMAIN, host_port_node_vm)}
                dev_reg = dr.async_get(self.hass)
                device = dev_reg.async_get_or_create(
                    config_entry_id=self.config_entry.entry_id,
                    identifiers=device_identifiers,
                )
                dev_reg.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )
                _LOGGER.debug("Device %s removed", device.name)

        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self._config,
            options=self.config_entry.options,
        )

        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        return self.async_abort(reason="changes_successful")


class ProxmoxVEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ProxmoxVE Config Flow class."""

    VERSION = 1
    _reauth_entry: config_entries.ConfigEntry | None = None

    def __init__(self):
        """Init for ProxmoxVE config flow."""
        super().__init__()

        self._config: dict[str, Any] = {}
        self._nodes: dict[str, Any] = {}
        self._host: str
        self._proxmox_client: ProxmoxClient | None = None

    async def async_step_import(self, import_config=None) -> FlowResult:
        """Import existing configuration."""

        errors = {}

        host = import_config.get(CONF_HOST, "")
        port = import_config.get(CONF_PORT, DEFAULT_PORT)
        username = import_config.get(CONF_USERNAME, "")
        password = import_config.get(CONF_PASSWORD, "")
        realm = import_config.get(CONF_REALM, DEFAULT_REALM)
        verify_ssl = import_config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

        self._host = host

        if port > 65535 or port <= 0:
            errors[CONF_PORT] = "invalid_port"

        if not errors:
            try:
                self._proxmox_client = ProxmoxClient(
                    host,
                    port=port,
                    user=username,
                    realm=realm,
                    password=password,
                    verify_ssl=verify_ssl,
                )

                await self.hass.async_add_executor_job(
                    self._proxmox_client.build_client
                )

            except proxmoxer.backends.https.AuthenticationError:
                errors[CONF_USERNAME] = "auth_error"
            except SSLError:
                errors[CONF_VERIFY_SSL] = "ssl_rejection"
            except ConnectTimeout:
                errors[CONF_HOST] = "cant_connect"
            except Exception:  # pylint: disable=broad-except
                errors[CONF_BASE] = "general_error"

            else:
                self._config[CONF_HOST] = host
                self._config[CONF_PORT] = port
                self._config[CONF_USERNAME] = username
                self._config[CONF_PASSWORD] = password
                self._config[CONF_REALM] = realm
                self._config[CONF_VERIFY_SSL] = verify_ssl

                for node in import_config.get(CONF_NODES):
                    self._config[CONF_NODE] = node["node"]
                    if await self._async_endpoint_exists(
                        f"{self._config[CONF_HOST]}/{self._config[CONF_PORT]}/{self._config[CONF_NODE]}"
                    ):
                        _LOGGER.warning(
                            "The node %s of instance %s:%s already configured, you can remove it from configuration.yaml if you still have it",
                            self._config[CONF_NODE],
                            self._config[CONF_HOST],
                            self._config[CONF_PORT],
                        )
                        return self.async_abort(reason="already_configured")

                    self._config[CONF_QEMU] = []
                    self._config[CONF_LXC] = []
                    for vm_id in node[CONF_VMS]:
                        self._config[CONF_QEMU].append(vm_id)
                    for container_id in node[CONF_CONTAINERS]:
                        self._config[CONF_LXC].append(container_id)

                    return self.async_create_entry(
                        title=f"{self._config[CONF_NODE]} - {self._config[CONF_HOST]}",
                        data=self._config,
                    )

        _LOGGER.error(
            "Could not import ProxmoxVE configuration, please configure it manually from Integrations"
        )
        return self.async_abort(reason="import_failed")

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Manual user configuration."""
        return await self.async_step_init(user_input)

    async def async_step_reauth(self, data: Mapping[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors = {}
        assert self._reauth_entry
        if user_input is not None:
            host = self._reauth_entry.data[CONF_HOST]
            port = self._reauth_entry.data[CONF_PORT]
            verify_ssl = self._reauth_entry.data[CONF_VERIFY_SSL]
            user = user_input.get(CONF_USERNAME)
            realm = user_input.get(CONF_REALM)
            password = user_input.get(CONF_PASSWORD)

            try:
                self._proxmox_client = ProxmoxClient(
                    host,
                    port=port,
                    user=user,
                    realm=realm,
                    password=password,
                    verify_ssl=verify_ssl,
                )

                await self.hass.async_add_executor_job(
                    self._proxmox_client.build_client
                )

            except proxmoxer.backends.https.AuthenticationError:
                errors[CONF_USERNAME] = "auth_error"
            except SSLError:
                errors[CONF_VERIFY_SSL] = "ssl_rejection"
            except ConnectTimeout:
                errors[CONF_HOST] = "cant_connect"
            except Exception:  # pylint: disable=broad-except
                errors[CONF_BASE] = "general_error"

            else:
                if CONF_HOST in self._reauth_entry.data:
                    user_input[CONF_HOST] = self._reauth_entry.data[CONF_HOST]
                if CONF_PORT in self._reauth_entry.data:
                    user_input[CONF_PORT] = self._reauth_entry.data[CONF_PORT]
                if CONF_VERIFY_SSL in self._reauth_entry.data:
                    user_input[CONF_VERIFY_SSL] = self._reauth_entry.data[
                        CONF_VERIFY_SSL
                    ]
                if CONF_NODE in self._reauth_entry.data:
                    user_input[CONF_NODE] = self._reauth_entry.data[CONF_NODE]
                if CONF_QEMU in self._reauth_entry.data:
                    user_input[CONF_QEMU] = self._reauth_entry.data[CONF_QEMU]
                if CONF_LXC in self._reauth_entry.data:
                    user_input[CONF_LXC] = self._reauth_entry.data[CONF_LXC]
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=self._reauth_entry.data[CONF_USERNAME],
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=self._reauth_entry.data[CONF_PASSWORD],
                    ): str,
                    vol.Optional(
                        CONF_REALM,
                        default=self._reauth_entry.data[CONF_REALM],
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_init(self, user_input) -> FlowResult:
        """Async step user for proxmoxve config flow."""
        return await self.async_step_host(user_input)

    async def async_step_host(self, user_input) -> FlowResult:
        """Async step of host config flow for proxmoxve."""
        errors = {}

        if user_input is not None:

            host = user_input.get(CONF_HOST, "")
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            username = user_input.get(CONF_USERNAME, "")
            password = user_input.get(CONF_PASSWORD, "")
            realm = user_input.get(CONF_REALM, DEFAULT_REALM)
            verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

            self._host = host

            if port > 65535 or port <= 0:
                errors[CONF_PORT] = "invalid_port"

            if not errors:

                try:
                    self._proxmox_client = ProxmoxClient(
                        host,
                        port=port,
                        user=username,
                        realm=realm,
                        password=password,
                        verify_ssl=verify_ssl,
                    )

                    await self.hass.async_add_executor_job(
                        self._proxmox_client.build_client
                    )

                except proxmoxer.backends.https.AuthenticationError:
                    errors[CONF_USERNAME] = "auth_error"
                except SSLError:
                    errors[CONF_VERIFY_SSL] = "ssl_rejection"
                except ConnectTimeout:
                    errors[CONF_HOST] = "cant_connect"
                except Exception:  # pylint: disable=broad-except
                    errors[CONF_BASE] = "general_error"

                else:
                    self._config[CONF_HOST] = host
                    self._config[CONF_PORT] = port
                    self._config[CONF_USERNAME] = username
                    self._config[CONF_PASSWORD] = password
                    self._config[CONF_REALM] = realm
                    self._config[CONF_VERIFY_SSL] = verify_ssl

                    return await self.async_step_node()

            if errors:
                data_schema = vol.Schema(
                    {
                        vol.Required(
                            CONF_HOST, default=user_input.get(CONF_HOST, "")
                        ): str,
                        vol.Required(
                            CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                        ): str,
                        vol.Required(
                            CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                        ): str,
                        vol.Optional(
                            CONF_REALM,
                            default=user_input.get(CONF_REALM, DEFAULT_REALM),
                        ): str,
                        vol.Optional(
                            CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                        ): int,
                        vol.Required(
                            CONF_VERIFY_SSL,
                            default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                        ): bool,
                    }
                )

                return self.async_show_form(
                    step_id="host", data_schema=data_schema, errors=errors
                )

        user_input = {}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                vol.Required(
                    CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                ): str,
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): str,
                vol.Optional(
                    CONF_REALM, default=user_input.get(CONF_REALM, DEFAULT_REALM)
                ): str,
                vol.Optional(
                    CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                ): int,
                vol.Required(
                    CONF_VERIFY_SSL,
                    default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="host", data_schema=data_schema, errors=errors
        )

    async def async_step_node(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the node selection step."""

        errors: dict[str, str] = {}

        if user_input:
            if await self._async_endpoint_exists(
                f"{self._config[CONF_HOST]}/{self._config[CONF_PORT]}/{user_input.get(CONF_NODE)}"
            ):
                return self.async_abort(reason="already_configured")

            node = user_input.get(CONF_NODE)
            self._config[CONF_NODE] = node
            return await self.async_step_selection_qemu_lxc(node=node)

        if (proxmox_cliente := self._proxmox_client) is not None:
            proxmox = proxmox_cliente.get_api_client()

        proxmox_nodes = await self.hass.async_add_executor_job(proxmox.nodes.get)

        nodes = []
        for node in proxmox_nodes:
            nodes.append(node["node"])

        if errors:
            return self.async_show_form(
                step_id="node",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NODE): vol.In(nodes),
                    }
                ),
                errors=errors,
            )

        return self.async_show_form(
            step_id="node",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NODE): vol.In(nodes),
                }
            ),
        )

    async def async_step_selection_qemu_lxc(
        self,
        user_input: dict[str, Any] | None = None,
        node: str | None = None,
    ) -> FlowResult:
        """Handle the QEMU/LXC selection step."""

        if user_input is None:
            if (proxmox_cliente := self._proxmox_client) is not None:
                proxmox = proxmox_cliente.get_api_client()

            qemu_list_for_multi_select: list[int] = [
                int(qemu[ID])
                for qemu in await self.hass.async_add_executor_job(
                    proxmox.nodes(node).qemu.get
                )
            ]
            lxc_list_for_multi_select: list[int] = [
                int(lxc[ID])
                for lxc in await self.hass.async_add_executor_job(
                    proxmox.nodes(node).lxc.get
                )
            ]

            return self.async_show_form(
                step_id="selection_qemu_lxc",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NODE): node,
                        vol.Optional(CONF_QEMU): cv.multi_select(
                            qemu_list_for_multi_select
                        ),
                        vol.Optional(CONF_LXC): cv.multi_select(
                            lxc_list_for_multi_select
                        ),
                    }
                ),
            )

        if CONF_QEMU not in self._config:
            self._config[CONF_QEMU] = []
        if (
            CONF_QEMU in user_input
            and (qemu_user := user_input.get(CONF_QEMU)) is not None
        ):
            for qemu_selection in qemu_user:
                self._config[CONF_QEMU].append(qemu_selection)

        if CONF_LXC not in self._config:
            self._config[CONF_LXC] = []
        if (
            CONF_LXC in user_input
            and (lxc_user := user_input.get(CONF_LXC)) is not None
        ):
            for lxc_selection in lxc_user:
                self._config[CONF_LXC].append(lxc_selection)

        return self.async_create_entry(
            title=f"{self._config[CONF_NODE]} - {self._config[CONF_HOST]}",
            data=self._config,
        )

    async def _async_endpoint_exists(self, host_port_node):
        existing_endpoints = [
            f"{entry.data.get(CONF_HOST)}/{entry.data.get(CONF_PORT)}/{entry.data.get(CONF_NODE)}"
            for entry in self._async_current_entries()
        ]

        return host_port_node in existing_endpoints

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Options callback for Proxmox."""
        return ProxmoxOptionsFlowHandler(config_entry)
