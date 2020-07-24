"""Config flow for ProxmoxVE integration."""

import logging

from proxmoxer.backends.https import AuthenticationError
from requests import ConnectTimeout
from requests.exceptions import ConnectionError as RConnectionError, SSLError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
import homeassistant.helpers.config_validation as cv

from . import ProxmoxClient
from .const import (  # pylint: disable=unused-import
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_TYPE,
    CONF_VMID,
    CONF_VMS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ProxmoxVEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ProxmoxVE config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize config flow."""
        super().__init__()

        self._config = {}
        self.proxmox_client = None

    # pylint: disable=signature-differs
    async def async_step_import(self, user_input=None):
        """Import config from configuration yaml file."""
        # the schema used in async_step_user differs from the deprecated CONFIG_SCHEMA, need to translate between the two.

        self._config[CONF_HOST] = user_input[CONF_HOST]
        self._config[CONF_USERNAME] = user_input[CONF_USERNAME]
        self._config[CONF_PASSWORD] = user_input[CONF_PASSWORD]

        self._config[CONF_VMS] = []

        virtual_machines = []

        for node in self._config[CONF_NODES]:
            for entity in node[CONF_VMS]:
                virtual_machines.append(
                    {
                        CONF_NODE: node[CONF_NODE],
                        CONF_VMID: entity[CONF_VMID],
                        CONF_TYPE: "qemu",
                    }
                )

            for entity in node[CONF_CONTAINERS]:
                virtual_machines.append(
                    {
                        CONF_NODE: node[CONF_NODE],
                        CONF_VMID: entity[CONF_VMID],
                        CONF_TYPE: "lxc",
                    }
                )

        title = self._config[CONF_HOST]

        # make sure vms exist before importing

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
        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="connection_error")

        all_vms = await self.hass.async_add_executor_job(
            self.proxmox_client.get_all_vms
        )

        for virt_man in virtual_machines:
            found = next((x for x in all_vms if virt_man[CONF_VMID] == x["id"]), None)

            if found:
                self._config[CONF_VMS].append(virt_man)
            else:
                _LOGGER.warning(
                    "Virtual machine %d not found in proxmox, make sure it exists.",
                    virt_man[CONF_VMID],
                )

        return self.async_create_entry(title=title, data=self._config)

    # pylint: disable=signature-differs
    async def async_step_user(self, user_input):
        """Handle a flow initialized by the user."""
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
            except (ConnectTimeout, RConnectionError):
                errors["base"] = "server_unreachable"
            except Exception:  # pylint: disable=broad-except
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
                    CONF_REALM, default=user_input.get(CONF_REALM, DEFAULT_REALM)
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
        """Step to select which VM to add to hass."""
        errors = {}

        vms = await self.hass.async_add_executor_job(self.proxmox_client.get_all_vms)

        def vm_config_from_string(vm_string):
            vmid = vm_string.split("-")[0].strip()
            vm_node = vm_string.split("-")[1].split(" (")[0].strip()

            for elem in vms:
                if elem["id"] == vmid and elem["node"] == vm_node:
                    return elem

            return None

        if user_input is not None:

            title = self._config[CONF_HOST]

            selected_vms = user_input.get(CONF_VMS)

            _LOGGER.debug(selected_vms)

            self._config[CONF_NODES] = []

            if CONF_VMS not in self._config:
                self._config[CONF_VMS] = []

            for virtual_machine in selected_vms:
                vm_entity = vm_config_from_string(virtual_machine)

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

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_VMS, default=user_input.get(CONF_VMS, available_vm)
                ): cv.multi_select(available_vm),
            }
        )

        return self.async_show_form(
            step_id="select_nodes_vms", data_schema=data_schema, errors=errors
        )
