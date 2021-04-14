"""Config Flow for ProxmoxVE."""
from proxmoxer.backends.https import AuthenticationError
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

from . import ProxmoxClient
from .const import (
    CONF_DEFAULT_REALM,
    CONF_REALM,
    DEFAULT_PORT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)


class ProxmoxVEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ProxmoxVE Config Flow class."""

    def __init__(self):
        """Init for ProxmoxVE config flow."""
        super().__init__()

        self._config = {}
        self._proxmox_client = None  # type: ProxmoxClient

    # pylint: disable=arguments-differ
    async def async_step_user(self, info):
        """Async step user for proxmoxve config flow."""
        errors = {}

        if info is not None:

            host = info.get(CONF_HOST, "")
            port = info.get(CONF_PORT, DEFAULT_PORT)
            username = info.get(CONF_USERNAME, "")
            password = info.get(CONF_PASSWORD, "")
            realm = info.get(CONF_REALM, CONF_DEFAULT_REALM)
            verify_ssl = info.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

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

            except AuthenticationError:
                errors[CONF_USERNAME] = "auth_error"
            except SSLError:
                errors[CONF_VERIFY_SSL] = "ssl_rejection"
            except ConnectTimeout:
                errors[CONF_HOST] = "cant_connect"
            except Exception:  # pylint: disable=broad-except
                errors[CONF_HOST] = "general_error"

            if not errors:
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

                return self.async_create_entry(title="ProxmoxVE", data=self._config)

        if info is None:
            info = {}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=info.get(CONF_HOST, "")): str,
                vol.Required(CONF_USERNAME, default=info.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=info.get(CONF_PASSWORD, "")): str,
                vol.Required(
                    CONF_REALM, default=info.get(CONF_REALM, CONF_DEFAULT_REALM)
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
