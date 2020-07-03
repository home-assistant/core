from homeassistant import config_entries
from .const import DOMAIN, CONF_REALM
import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_VERIFY_SSL,
)

from .const import CONF_NODES, CONF_VMS, CONF_VMID, CONF_TYPE, CONF_NODE

from proxmoxer.backends.https import AuthenticationError
from requests import ConnectTimeout
from requests.exceptions import SSLError, ConnectionError
import homeassistant.helpers.config_validation as cv

from . import ProxmoxClient

import voluptuous as vol


DEFAULT_PORT = 8006
DEFAULT_VERIFY_SSL = True

_LOGGER = logging.getLogger(__name__)


class ProxmoxVEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ProxmoxVE config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        super().__init__()

        self._selected_nodes = []
        self._selected_vms = []

        self._config = {}

    async def async_step_user(self, user_input):
        errors = {}

        if user_input is not None:
            self._config[CONF_HOST] = user_input.get(CONF_HOST)
            self._config[CONF_PORT] = user_input.get(CONF_PORT)
            self._config[CONF_USERNAME] = user_input.get(CONF_USERNAME)
            self._config[CONF_PASSWORD] = user_input.get(CONF_PASSWORD)
            self._config[CONF_REALM] = user_input.get(CONF_REALM)
            self._config[CONF_VERIFY_SSL] = user_input.get(CONF_VERIFY_SSL)

            self.proxmox_client = ProxmoxClient(
                self._config[CONF_HOST],
                self._config[CONF_PORT],
                self._config[CONF_USERNAME],
                self._config[CONF_REALM],
                self._config[CONF_PASSWORD],
                self._config[CONF_VERIFY_SSL],
            )

            try:
                await self.hass.async_add_executor_job(self.proxmox_client.build_client)
            except AuthenticationError:
                errors["base"] = "auth_error"
            except SSLError:
                errors["base"] = "ssl_error"
            except (ConnectTimeout, ConnectionError):
                errors["base"] = "server_unreachable"
            except Exception as e:
                errors["base"] = "generic_error"
                _LOGGER.exception("ProxmoxVE generic error")

            if not errors:
                _LOGGER.info("ProxmoxVE login successful, go to next page")
                return await self.async_step_select_nodes_vms(None)

        if user_input is None:
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
                vol.Required(
                    CONF_REALM, default=user_input.get(CONF_REALM, "pve")
                ): str,
                vol.Optional(
                    CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                ): int,
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors,
        )

    async def async_step_select_nodes_vms(self, user_input):
        errors = {}

        vms = await self.hass.async_add_executor_job(self.proxmox_client.get_all_vms)
        nodes = await self.hass.async_add_executor_job(self.proxmox_client.get_nodes)

        def vm_config_from_string(vm_string):
            id = vm_string.split("-")[0].strip()
            vm_node = vm_string.split("-")[1].split(" (")[0].strip()

            for vm in vms:
                if vm["id"] == id and vm["node"] == vm_node:
                    return vm

            return None

        if user_input is not None:

            title = self._config[CONF_HOST]

            selected_nodes = user_input.get(CONF_NODES)
            selected_vms = user_input.get(CONF_VMS)

            _LOGGER.debug(selected_vms)

            self._config[CONF_NODES] = []

            for node in selected_nodes:
                self._config[CONF_NODES].append(node)

            if CONF_VMS not in self._config:
                self._config[CONF_VMS] = []

            for vm in selected_vms:
                vm_entity = vm_config_from_string(vm)

                if vm_entity is None:
                    errors["base"] = "generic_error"
                    _LOGGER.error("Could not find selected vm in vm list")
                    break

                self._config[CONF_VMS].append(
                    {
                        CONF_NODE: vm_entity["node"],
                        CONF_VMID: vm_entity["id"],
                        CONF_TYPE: vm_entity["type"],
                    }
                )

            _LOGGER.debug(self._config)

            if not errors:
                return self.async_create_entry(title=title, data=self._config)

        if user_input is None:
            user_input = {}

        _LOGGER.debug(vms)

        available_vm = [
            f'{n.get("id")} - {n.get("node")} ({n.get("name")})' for n in vms
        ]

        _LOGGER.debug(nodes)

        available_nodes = [n.get("name") for n in nodes]

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_VMS, default=user_input.get(CONF_VMS, available_vm)
                ): cv.multi_select(available_vm),
                vol.Optional(
                    CONF_NODES, default=user_input.get(CONF_NODES, available_nodes)
                ): cv.multi_select(available_nodes),
            }
        )

        return self.async_show_form(
            step_id="select_nodes_vms", data_schema=data_schema, errors=errors
        )
