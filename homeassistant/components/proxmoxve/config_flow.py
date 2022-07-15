"""Config Flow for ProxmoxVE."""
import logging

import proxmoxer
from requests.exceptions import ConnectTimeout, SSLError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult

from . import ProxmoxClient
from .const import CONF_REALM, DEFAULT_PORT, DEFAULT_REALM, DEFAULT_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ProxmoxVEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ProxmoxVE Config Flow class."""

    VERSION = 1

    def __init__(self):
        """Init for ProxmoxVE config flow."""
        super().__init__()

        self._config = {}
        self._proxmox_client = None

    async def async_step_import(self, import_config=None):
        """Import existing configuration."""
        return await self.async_step_init(import_config, True)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Manual user configuration."""
        return await self.async_step_init(user_input, False)

    async def async_step_init(self, info, is_import):
        """Async step user for proxmoxve config flow."""
        errors = {}

        if info is not None:

            host = info.get(CONF_HOST, "")
            port = info.get(CONF_PORT, DEFAULT_PORT)
            username = info.get(CONF_USERNAME, "")
            password = info.get(CONF_PASSWORD, "")
            realm = info.get(CONF_REALM, DEFAULT_REALM)
            verify_ssl = info.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

            if await self._async_endpoint_exists(f"{host}/{port}"):
                _LOGGER.info(
                    "Device %s already configured, you can remove it from configuration.yaml if you still have it",
                    host,
                )
                return self.async_abort(reason="already_configured")

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
                    errors["base"] = "general_error"

                else:
                    # get all vms and containers and add them

                    if "nodes" not in self._config:
                        self._config["nodes"] = []

                    self._config[CONF_HOST] = host
                    self._config[CONF_PORT] = port
                    self._config[CONF_USERNAME] = username
                    self._config[CONF_PASSWORD] = password
                    self._config[CONF_REALM] = realm
                    self._config[CONF_VERIFY_SSL] = verify_ssl

                    await self.hass.async_add_executor_job(self._add_vms_to_config)

                    return self.async_create_entry(title=host, data=self._config)

            if errors and not is_import:
                data_schema = vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=info.get(CONF_HOST, "")): str,
                        vol.Required(
                            CONF_USERNAME, default=info.get(CONF_USERNAME, "")
                        ): str,
                        vol.Required(
                            CONF_PASSWORD, default=info.get(CONF_PASSWORD, "")
                        ): str,
                        vol.Required(
                            CONF_REALM, default=info.get(CONF_REALM, DEFAULT_REALM)
                        ): str,
                        vol.Required(
                            CONF_PORT, default=info.get(CONF_PORT, DEFAULT_PORT)
                        ): int,
                        vol.Required(
                            CONF_VERIFY_SSL,
                            default=info.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                        ): bool,
                    }
                )

                return self.async_show_form(
                    step_id="user", data_schema=data_schema, errors=errors
                )

        info = {}

        if errors and is_import:
            _LOGGER.error(
                "Could not import ProxmoxVE configuration, please configure it manually from Integrations"
            )
            return self.async_abort(reason="import_failed")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=info.get(CONF_HOST, "")): str,
                vol.Required(CONF_USERNAME, default=info.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=info.get(CONF_PASSWORD, "")): str,
                vol.Required(
                    CONF_REALM, default=info.get(CONF_REALM, DEFAULT_REALM)
                ): str,
                vol.Required(CONF_PORT, default=info.get(CONF_PORT, DEFAULT_PORT)): int,
                vol.Required(
                    CONF_VERIFY_SSL,
                    default=info.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def _async_endpoint_exists(self, hostid):
        existing_endpoints = [
            f"{entry.data.get(CONF_HOST)}/{entry.data.get(CONF_PORT)}"
            for entry in self._async_current_entries()
        ]

        return hostid in existing_endpoints

    def _add_vms_to_config(self):
        proxmox = self._proxmox_client.get_api_client()

        for node in proxmox.nodes.get():

            vms = []
            containers = []

            for virtman in proxmox.nodes(node["node"]).qemu.get():
                vms.append(virtman["vmid"])

            for cont in proxmox.nodes(node["node"]).lxc.get():
                containers.append(cont["vmid"])

            self._config["nodes"].append(
                {"name": node["node"], "vms": vms, "containers": containers}
            )
