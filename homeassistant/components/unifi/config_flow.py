"""Config flow for UniFi."""
import socket
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CONTROLLER,
    CONF_DETECTION_TIME,
    CONF_DPI_RESTRICTIONS,
    CONF_IGNORE_WIRED_BUG,
    CONF_POE_CLIENTS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    CONTROLLER_ID,
    DEFAULT_DPI_RESTRICTIONS,
    DEFAULT_POE_CLIENTS,
    DOMAIN as UNIFI_DOMAIN,
    LOGGER,
)
from .controller import get_controller
from .errors import AuthenticationRequired, CannotConnect

DEFAULT_PORT = 443
DEFAULT_SITE_ID = "default"
DEFAULT_VERIFY_SSL = False


MODEL_PORTS = {
    "UniFi Dream Machine": 443,
    "UniFi Dream Machine Pro": 443,
}


@callback
def get_controller_id_from_config_entry(config_entry):
    """Return controller with a matching bridge id."""
    return CONTROLLER_ID.format(
        host=config_entry.data[CONF_CONTROLLER][CONF_HOST],
        site=config_entry.data[CONF_CONTROLLER][CONF_SITE_ID],
    )


class UnifiFlowHandler(config_entries.ConfigFlow, domain=UNIFI_DOMAIN):
    """Handle a UniFi config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return UnifiOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the UniFi flow."""
        self.config = {}
        self.sites = None
        self.reauth_config_entry = None
        self.reauth_config = {}
        self.reauth_schema = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            try:
                self.config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_PORT: user_input.get(CONF_PORT),
                    CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
                    CONF_SITE_ID: DEFAULT_SITE_ID,
                }

                controller = await get_controller(self.hass, **self.config)

                sites = await controller.sites()
                self.sites = {site["name"]: site["desc"] for site in sites.values()}

                if self.reauth_config.get(CONF_SITE_ID) in self.sites:
                    return await self.async_step_site(
                        {CONF_SITE_ID: self.reauth_config[CONF_SITE_ID]}
                    )

                return await self.async_step_site()

            except AuthenticationRequired:
                errors["base"] = "faulty_credentials"

            except CannotConnect:
                errors["base"] = "service_unavailable"

            except Exception:  # pylint: disable=broad-except
                LOGGER.error(
                    "Unknown error connecting with UniFi Controller at %s",
                    user_input[CONF_HOST],
                )
                return self.async_abort(reason="unknown")

        host = self.config.get(CONF_HOST)
        if not host and await async_discover_unifi(self.hass):
            host = "unifi"

        data = self.reauth_schema or {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(
                CONF_PORT, default=self.config.get(CONF_PORT, DEFAULT_PORT)
            ): int,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data),
            errors=errors,
        )

    async def async_step_site(self, user_input=None):
        """Select site to control."""
        errors = {}

        if user_input is not None:

            self.config[CONF_SITE_ID] = user_input[CONF_SITE_ID]
            data = {CONF_CONTROLLER: self.config}

            if self.reauth_config_entry:
                self.hass.config_entries.async_update_entry(
                    self.reauth_config_entry, data=data
                )
                await self.hass.config_entries.async_reload(
                    self.reauth_config_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

            for config_entry in self._async_current_entries():
                controller_data = config_entry.data[CONF_CONTROLLER]
                if (
                    controller_data[CONF_HOST] != self.config[CONF_HOST]
                    or controller_data[CONF_SITE_ID] != self.config[CONF_SITE_ID]
                ):
                    continue

                controller = self.hass.data.get(UNIFI_DOMAIN, {}).get(
                    config_entry.entry_id
                )

                if controller and controller.available:
                    return self.async_abort(reason="already_configured")

                self.hass.config_entries.async_update_entry(config_entry, data=data)
                await self.hass.config_entries.async_reload(config_entry.entry_id)
                return self.async_abort(reason="configuration_updated")

            site_nice_name = self.sites[self.config[CONF_SITE_ID]]
            return self.async_create_entry(title=site_nice_name, data=data)

        if len(self.sites) == 1:
            return await self.async_step_site({CONF_SITE_ID: next(iter(self.sites))})

        return self.async_show_form(
            step_id="site",
            data_schema=vol.Schema({vol.Required(CONF_SITE_ID): vol.In(self.sites)}),
            errors=errors,
        )

    async def async_step_reauth(self, config_entry: dict):
        """Trigger a reauthentication flow."""
        self.reauth_config_entry = config_entry
        self.reauth_config = config_entry.data[CONF_CONTROLLER]

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            CONF_HOST: self.reauth_config[CONF_HOST],
            CONF_SITE_ID: config_entry.title,
        }

        self.reauth_schema = {
            vol.Required(CONF_HOST, default=self.reauth_config[CONF_HOST]): str,
            vol.Required(CONF_USERNAME, default=self.reauth_config[CONF_USERNAME]): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=self.reauth_config[CONF_PORT]): int,
            vol.Required(
                CONF_VERIFY_SSL, default=self.reauth_config[CONF_VERIFY_SSL]
            ): bool,
        }

        return await self.async_step_user()

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered unifi device."""
        parsed_url = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION])
        model_description = discovery_info[ssdp.ATTR_UPNP_MODEL_DESCRIPTION]
        mac_address = format_mac(discovery_info[ssdp.ATTR_UPNP_SERIAL])

        self.config = {
            CONF_HOST: parsed_url.hostname,
        }

        if self._host_already_configured(self.config[CONF_HOST]):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self.config[CONF_HOST]})

        # pylint: disable=no-member
        self.context["title_placeholders"] = {
            CONF_HOST: self.config[CONF_HOST],
            CONF_SITE_ID: "default",
        }

        port = MODEL_PORTS.get(model_description)
        if port is not None:
            self.config[CONF_PORT] = port

        return await self.async_step_user()

    def _host_already_configured(self, host):
        """See if we already have a unifi entry matching the host."""
        for entry in self._async_current_entries():
            if not entry.data:
                continue
            if entry.data[CONF_CONTROLLER][CONF_HOST] == host:
                return True
        return False


class UnifiOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Unifi options."""

    def __init__(self, config_entry):
        """Initialize UniFi options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.controller = None

    async def async_step_init(self, user_input=None):
        """Manage the UniFi options."""
        self.controller = self.hass.data[UNIFI_DOMAIN][self.config_entry.entry_id]
        self.options[CONF_BLOCK_CLIENT] = self.controller.option_block_clients

        if self.show_advanced_options:
            return await self.async_step_device_tracker()

        return await self.async_step_simple_options()

    async def async_step_simple_options(self, user_input=None):
        """For simple Jack."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        clients_to_block = {}

        for client in self.controller.api.clients.values():
            clients_to_block[
                client.mac
            ] = f"{client.name or client.hostname} ({client.mac})"

        return self.async_show_form(
            step_id="simple_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TRACK_CLIENTS,
                        default=self.controller.option_track_clients,
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_DEVICES,
                        default=self.controller.option_track_devices,
                    ): bool,
                    vol.Optional(
                        CONF_BLOCK_CLIENT, default=self.options[CONF_BLOCK_CLIENT]
                    ): cv.multi_select(clients_to_block),
                }
            ),
        )

    async def async_step_device_tracker(self, user_input=None):
        """Manage the device tracker options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_client_control()

        ssids = (
            set(self.controller.api.wlans)
            | {
                f"{wlan.name}{wlan.name_combine_suffix}"
                for wlan in self.controller.api.wlans.values()
                if not wlan.name_combine_enabled
            }
            | {
                wlan["name"]
                for ap in self.controller.api.devices.values()
                for wlan in ap.wlan_overrides
                if "name" in wlan
            }
        )
        ssid_filter = {ssid: ssid for ssid in sorted(list(ssids))}

        return self.async_show_form(
            step_id="device_tracker",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TRACK_CLIENTS,
                        default=self.controller.option_track_clients,
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_WIRED_CLIENTS,
                        default=self.controller.option_track_wired_clients,
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_DEVICES,
                        default=self.controller.option_track_devices,
                    ): bool,
                    vol.Optional(
                        CONF_SSID_FILTER, default=self.controller.option_ssid_filter
                    ): cv.multi_select(ssid_filter),
                    vol.Optional(
                        CONF_DETECTION_TIME,
                        default=int(
                            self.controller.option_detection_time.total_seconds()
                        ),
                    ): int,
                    vol.Optional(
                        CONF_IGNORE_WIRED_BUG,
                        default=self.controller.option_ignore_wired_bug,
                    ): bool,
                }
            ),
        )

    async def async_step_client_control(self, user_input=None):
        """Manage configuration of network access controlled clients."""
        errors = {}

        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_statistics_sensors()

        clients_to_block = {}

        for client in self.controller.api.clients.values():
            clients_to_block[
                client.mac
            ] = f"{client.name or client.hostname} ({client.mac})"

        return self.async_show_form(
            step_id="client_control",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BLOCK_CLIENT, default=self.options[CONF_BLOCK_CLIENT]
                    ): cv.multi_select(clients_to_block),
                    vol.Optional(
                        CONF_POE_CLIENTS,
                        default=self.options.get(CONF_POE_CLIENTS, DEFAULT_POE_CLIENTS),
                    ): bool,
                    vol.Optional(
                        CONF_DPI_RESTRICTIONS,
                        default=self.options.get(
                            CONF_DPI_RESTRICTIONS, DEFAULT_DPI_RESTRICTIONS
                        ),
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_statistics_sensors(self, user_input=None):
        """Manage the statistics sensors options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="statistics_sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ALLOW_BANDWIDTH_SENSORS,
                        default=self.controller.option_allow_bandwidth_sensors,
                    ): bool,
                    vol.Optional(
                        CONF_ALLOW_UPTIME_SENSORS,
                        default=self.controller.option_allow_uptime_sensors,
                    ): bool,
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(title="", data=self.options)


async def async_discover_unifi(hass):
    """Discover UniFi address."""
    try:
        return await hass.async_add_executor_job(socket.gethostbyname, "unifi")
    except socket.gaierror:
        return None
