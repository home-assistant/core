"""Config flow for UniFi Network integration.

Provides user initiated configuration flow.
Discovery of UniFi Network instances through unifi_discovery.
Reauthentication when issue with credentials are reported.
Configuration of options through options flow.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import operator
import socket
from types import MappingProxyType
from typing import Any, override

import aiounifi
from aiounifi.interfaces.sites import Sites
from aiounifi.network.v1.models.site import Site as NetworkSite
import probatio

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, SectionConfig, section
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import DiscoveryInfoType

from . import UnifiConfigEntry
from .const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CLIENT_SOURCE,
    CONF_CONNECTION_MODE,
    CONF_DETECTION_TIME,
    CONF_DPI_RESTRICTIONS,
    CONF_IGNORE_LOCAL_MAC,
    CONF_IGNORE_WIRED_BUG,
    CONF_MORE_OPTIONS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    CONNECTION_MODE_API_KEY,
    CONNECTION_MODE_LOCAL_USER,
    DEFAULT_DPI_RESTRICTIONS,
    DOMAIN,
)
from .errors import AuthenticationRequired, CannotConnect
from .hub import UnifiHub, get_unifi_api

DEFAULT_HOST = "unifi"
DEFAULT_PORT = 443
DEFAULT_SITE_ID = "default"
DEFAULT_VERIFY_SSL = False

API_KEY_DOCUMENTATION_URL = "https://www.home-assistant.io/integrations/unifi/#api-key"
API_KEY_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


class UnifiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a UniFi Network config flow."""

    VERSION = 1

    sites: Sites
    network_sites: dict[str, NetworkSite]
    """Sites of the Network Integration API by UUID, when set up with a key."""

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: UnifiConfigEntry,
    ) -> UnifiOptionsFlowHandler:
        """Get the options flow for this handler."""
        return UnifiOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize the UniFi Network flow."""
        self.config: dict[str, Any] = {}
        self.reauth_schema: dict[probatio.Marker, Any] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to connect: with a local user or with an API key."""
        return self.async_show_menu(
            step_id="user", menu_options=["local_user", "api_key"]
        )

    async def async_step_local_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up with the username and password of a local user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.config = _config_from_input(user_input)
            data_schema = self._build_form_schema(
                self.config[CONF_HOST],
                self.config[CONF_USERNAME],
                self.config[CONF_PORT],
                self.config[CONF_VERIFY_SSL],
            )

            with _catch_unifi_api_flow_errors(errors):
                self.sites = await self._async_update_sites(self.config)
                return await self.async_step_site()
        else:
            host = self.config.get(CONF_HOST)
            if not host:
                host = await _async_discover_unifi(self.hass)
            if not host:
                host = DEFAULT_HOST
            data_schema = self._build_form_schema(
                host=host,
                verify_ssl=self.config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            )

        return self.async_show_form(
            step_id="local_user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up with an API key of the Network Integration API.

        The only option on consoles that cannot hold local users, such as
        members of a UniFi fabric. Fewer entities are available this way.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            self.config = _config_from_api_key_input(user_input)
            data_schema = _build_api_key_schema(
                self.config[CONF_HOST],
                self.config[CONF_PORT],
                self.config[CONF_VERIFY_SSL],
            )

            with _catch_unifi_api_flow_errors(errors, CONF_API_KEY):
                self.network_sites = await self._async_update_network_sites(self.config)
                return await self.async_step_network_site()
        else:
            host = self.config.get(CONF_HOST)
            if not host:
                host = await _async_discover_unifi(self.hass)
            if not host:
                host = DEFAULT_HOST
            data_schema = _build_api_key_schema(
                host=host,
                verify_ssl=self.config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            )

        return self.async_show_form(
            step_id="api_key",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "api_key_documentation_url": API_KEY_DOCUMENTATION_URL
            },
        )

    async def async_step_network_site(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the site to control, among those the API key can see."""
        if user_input is not None:
            site = self.network_sites[user_input[CONF_SITE_ID]]
            self.config[CONF_SITE_ID] = site.internal_reference

            await self.async_set_unique_id(site.site_id)
            self._abort_if_unique_id_configured()
            self._abort_if_site_configured()

            return self.async_create_entry(title=site.name, data=self.config)

        if len(self.network_sites) == 1:
            return await self.async_step_network_site(
                {CONF_SITE_ID: next(iter(self.network_sites))}
            )

        site_names = {site.site_id: site.name for site in self.network_sites.values()}
        return self.async_show_form(
            step_id="network_site",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_SITE_ID): probatio.In(site_names)}
            ),
        )

    async def async_step_site(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select site to control."""
        if user_input is not None:
            unique_id = user_input[CONF_SITE_ID]
            self.config[CONF_SITE_ID] = self.sites[unique_id].name

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            self._abort_if_site_configured()

            site_nice_name = self.sites[unique_id].description
            return self.async_create_entry(title=site_nice_name, data=self.config)

        if len(self.sites.values()) == 1:
            return await self.async_step_site({CONF_SITE_ID: next(iter(self.sites))})

        site_names = {site.site_id: site.description for site in self.sites.values()}
        return self.async_show_form(
            step_id="site",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_SITE_ID): probatio.In(site_names)}
            ),
        )

    @callback
    def _abort_if_site_configured(self) -> None:
        """Abort if the site is already set up in the other connection mode.

        A site has one unique ID per mode: the classic API's site `_id` and
        the Integration API's site UUID. Entities of both modes share their
        unique IDs, so a second entry for the same site would only produce
        duplicates. Host and short site name are the same in both modes.
        """
        self._async_abort_entries_match(
            {CONF_HOST: self.config[CONF_HOST], CONF_SITE_ID: self.config[CONF_SITE_ID]}
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger a reauthentication flow."""
        reauth_entry = self._get_reauth_entry()
        self.context["title_placeholders"] = {
            CONF_HOST: reauth_entry.data[CONF_HOST],
            CONF_NAME: reauth_entry.title,
        }

        if reauth_entry.data.get(CONF_CONNECTION_MODE) == CONNECTION_MODE_API_KEY:
            return await self.async_step_reauth_api_key()
        return await self.async_step_reconfigure()

    async def async_step_reauth_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            config_data = {**reauth_entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}
            with _catch_unifi_api_flow_errors(errors, CONF_API_KEY):
                sites = await self._async_update_network_sites(config_data)
                if reauth_entry.unique_id not in sites:
                    raise AbortFlow("unknown_site_id")
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )

        return self.async_show_form(
            step_id="reauth_api_key",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_API_KEY): API_KEY_SELECTOR}
            ),
            errors=errors,
            description_placeholders={
                "api_key_documentation_url": API_KEY_DOCUMENTATION_URL
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        config_entry = self._get_reauth_or_reconfigure_entry()
        if config_entry.data.get(CONF_CONNECTION_MODE) == CONNECTION_MODE_API_KEY:
            return await self.async_step_reconfigure_api_key(user_input)
        errors: dict[str, str] = {}

        if user_input is not None:
            config_data = _config_from_input(user_input)
            data_schema = self._build_form_schema(
                config_data[CONF_HOST],
                config_data[CONF_USERNAME],
                config_data[CONF_PORT],
                config_data[CONF_VERIFY_SSL],
            )

            with _catch_unifi_api_flow_errors(errors):
                sites = await self._async_update_sites(config_data)

                if (
                    (unique_id := config_entry.unique_id) is not None
                ) and unique_id in sites:
                    config_data[CONF_SITE_ID] = sites[unique_id].name
                    return self.async_update_reload_and_abort(
                        config_entry, data_updates=config_data
                    )
                raise AbortFlow("unknown_site_id")
        else:
            data_schema = self._build_form_schema(
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_USERNAME],
                config_entry.data[CONF_PORT],
                config_entry.data[CONF_VERIFY_SSL],
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address or API key of an entry set up with an API key.

        The site stays the same: the entry's unique ID is its UUID and must be
        among the sites the new key can see.
        """
        config_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            config_data = _config_from_api_key_input(user_input)
            data_schema = _build_api_key_schema(
                config_data[CONF_HOST],
                config_data[CONF_PORT],
                config_data[CONF_VERIFY_SSL],
            )

            with _catch_unifi_api_flow_errors(errors, CONF_API_KEY):
                sites = await self._async_update_network_sites(config_data)
                if (site := sites.get(config_entry.unique_id or "")) is None:
                    raise AbortFlow("unknown_site_id")
                config_data[CONF_SITE_ID] = site.internal_reference
                return self.async_update_reload_and_abort(
                    config_entry, data_updates=config_data
                )
        else:
            data_schema = _build_api_key_schema(
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_PORT],
                config_entry.data[CONF_VERIFY_SSL],
            )

        return self.async_show_form(
            step_id="reconfigure_api_key",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "api_key_documentation_url": API_KEY_DOCUMENTATION_URL
            },
        )

    @override
    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle discovery via unifi_discovery."""
        source_ip = discovery_info["source_ip"]
        if not source_ip:
            return self.async_abort(reason="cannot_connect")
        mac_address = format_mac(discovery_info["hw_addr"])
        direct_connect_domain = discovery_info.get("direct_connect_domain")
        host = direct_connect_domain or source_ip

        self.config = {
            CONF_HOST: host,
            CONF_VERIFY_SSL: bool(direct_connect_domain),
        }

        # MAC first: an entry keyed by it gets its host refreshed here, and the
        # host match below would otherwise abort before that can happen.
        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(updates=self.config, reload_on_update=False)

        # A console answers on every VLAN interface but discovery reports only
        # one of them, so match every address it announced for itself.
        known_hosts = {source_ip, *discovery_info.get("announced_ips", ())}
        if direct_connect_domain:
            known_hosts.add(direct_connect_domain)
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data.get(CONF_HOST) in known_hosts:
                return self.async_abort(reason="already_configured")

        self.context["title_placeholders"] = {
            CONF_NAME: (
                discovery_info.get("name")
                or discovery_info.get("hostname")
                or discovery_info.get("product_name")
                or "UniFi Network"
            ),
            CONF_HOST: source_ip,
        }
        self.context["configuration_url"] = f"https://{host}"

        return await self.async_step_user()

    def _build_form_schema(
        self,
        host: str = DEFAULT_HOST,
        username: str = "",
        port: int = DEFAULT_PORT,
        verify_ssl: bool = DEFAULT_VERIFY_SSL,
    ) -> probatio.Schema:
        return probatio.Schema(
            {
                probatio.Required(CONF_HOST, default=host): str,
                probatio.Required(CONF_USERNAME, default=username): str,
                probatio.Required(CONF_PASSWORD): str,
                probatio.Optional(CONF_PORT, default=port): int,
                probatio.Optional(
                    CONF_VERIFY_SSL,
                    default=verify_ssl,
                ): bool,
            }
        )

    async def _async_update_network_sites(
        self, data: Mapping[str, Any]
    ) -> dict[str, NetworkSite]:
        """Get the sites an API key can see, by UUID."""
        api = await get_unifi_api(self.hass, MappingProxyType(data))
        await api.network.sites.update()
        return dict(api.network.sites.items())

    async def _async_update_sites(self, data: Mapping[str, Any]) -> Sites:
        """Get updated sites through UniFi API."""
        hub = await get_unifi_api(self.hass, MappingProxyType(data))
        await hub.sites.update()
        return hub.sites

    @callback
    def _get_reauth_or_reconfigure_entry(self) -> ConfigEntry:
        """Return the config entry the current flow is modifying."""
        if self.source == SOURCE_REAUTH:
            return self._get_reauth_entry()
        return self._get_reconfigure_entry()


class UnifiOptionsFlowHandler(OptionsFlow):
    """Handle Unifi Network options."""

    hub: UnifiHub

    def __init__(self, config_entry: UnifiConfigEntry) -> None:
        """Initialize UniFi Network options flow."""
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the UniFi Network options."""
        self.hub = self.config_entry.runtime_data
        self.options[CONF_BLOCK_CLIENT] = self.hub.config.option_block_clients

        if user_input is not None:
            more_options = user_input.pop(CONF_MORE_OPTIONS, {})
            user_input.update(more_options)
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        clients_to_block: dict[str, str] = {}
        if self.hub.config.uses_api_key:
            # The Integration API cannot block a client, so none is offered
            clients = {
                mac: f"{client.name or 'Unknown'} ({mac})"
                for mac, client in self.hub.api.network.clients.items()
            }
        else:
            for client in self.hub.api.clients.values():
                clients_to_block[client.mac] = (
                    f"{client.name or client.hostname} ({client.mac})"
                )
            clients = {
                client.mac: f"{client.name or client.hostname} ({client.mac})"
                for client in self.hub.api.clients.values()
            }

        selected_clients_to_block = [
            client
            for client in self.options.get(CONF_BLOCK_CLIENT, [])
            if client in clients_to_block
        ]

        clients |= {
            mac: f"Unknown ({mac})"
            for mac in self.options.get(CONF_CLIENT_SOURCE, [])
            if mac not in clients
        }

        ssids = (
            {wlan.name for wlan in self.hub.api.wlans.values()}
            | {
                f"{wlan.name}{wlan.name_combine_suffix}"
                for wlan in self.hub.api.wlans.values()
                if not wlan.name_combine_enabled
                and wlan.name_combine_suffix is not None
            }
            | {
                wlan["name"]
                for ap in self.hub.api.devices.values()
                for wlan in ap.wlan_overrides
                if "name" in wlan
            }
        )
        ssid_filter = {ssid: ssid for ssid in sorted(ssids)}

        selected_ssids_to_filter = [
            ssid for ssid in self.hub.config.option_ssid_filter if ssid in ssid_filter
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_TRACK_CLIENTS,
                        default=self.hub.config.option_track_clients,
                    ): bool,
                    probatio.Optional(
                        CONF_TRACK_DEVICES,
                        default=self.hub.config.option_track_devices,
                    ): bool,
                    probatio.Optional(
                        CONF_BLOCK_CLIENT, default=selected_clients_to_block
                    ): cv.multi_select(clients_to_block),
                    probatio.Required(CONF_MORE_OPTIONS): section(
                        probatio.Schema(
                            {
                                probatio.Optional(
                                    CONF_CLIENT_SOURCE,
                                    default=self.options.get(CONF_CLIENT_SOURCE, []),
                                ): cv.multi_select(
                                    dict(
                                        sorted(
                                            clients.items(),
                                            key=operator.itemgetter(1),
                                        )
                                    )
                                ),
                                probatio.Optional(
                                    CONF_TRACK_WIRED_CLIENTS,
                                    default=self.hub.config.option_track_wired_clients,
                                ): bool,
                                probatio.Optional(
                                    CONF_SSID_FILTER,
                                    default=selected_ssids_to_filter,
                                ): cv.multi_select(ssid_filter),
                                probatio.Optional(
                                    CONF_DETECTION_TIME,
                                    default=int(
                                        self.hub.config.option_detection_time.total_seconds()
                                    ),
                                ): int,
                                probatio.Optional(
                                    CONF_IGNORE_WIRED_BUG,
                                    default=self.hub.config.option_ignore_wired_bug,
                                ): bool,
                                probatio.Optional(
                                    CONF_IGNORE_LOCAL_MAC,
                                    default=self.hub.config.option_ignore_local_mac,
                                ): bool,
                                probatio.Optional(
                                    CONF_DPI_RESTRICTIONS,
                                    default=self.options.get(
                                        CONF_DPI_RESTRICTIONS,
                                        DEFAULT_DPI_RESTRICTIONS,
                                    ),
                                ): bool,
                                probatio.Optional(
                                    CONF_ALLOW_BANDWIDTH_SENSORS,
                                    default=self.hub.config.option_allow_bandwidth_sensors,
                                ): bool,
                                probatio.Optional(
                                    CONF_ALLOW_UPTIME_SENSORS,
                                    default=self.hub.config.option_allow_uptime_sensors,
                                ): bool,
                            }
                        ),
                        SectionConfig(collapsed=True),
                    ),
                }
            ),
            last_step=True,
        )


async def _async_discover_unifi(hass: HomeAssistant) -> str | None:
    """Discover UniFi Network address."""
    try:
        return await hass.async_add_executor_job(socket.gethostbyname, "unifi")
    except socket.gaierror:
        return None


def _config_from_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build config entry data from user input."""
    return {
        CONF_HOST: user_input[CONF_HOST],
        CONF_CONNECTION_MODE: CONNECTION_MODE_LOCAL_USER,
        CONF_USERNAME: user_input[CONF_USERNAME],
        CONF_PASSWORD: user_input[CONF_PASSWORD],
        CONF_PORT: user_input.get(CONF_PORT),
        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
        CONF_SITE_ID: DEFAULT_SITE_ID,
    }


def _config_from_api_key_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build config entry data from the API key form."""
    return {
        CONF_HOST: user_input[CONF_HOST],
        CONF_CONNECTION_MODE: CONNECTION_MODE_API_KEY,
        CONF_API_KEY: user_input[CONF_API_KEY],
        CONF_PORT: user_input.get(CONF_PORT, DEFAULT_PORT),
        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        CONF_SITE_ID: DEFAULT_SITE_ID,
    }


def _build_api_key_schema(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    verify_ssl: bool = DEFAULT_VERIFY_SSL,
) -> probatio.Schema:
    """Schema of the API key form."""
    return probatio.Schema(
        {
            probatio.Required(CONF_HOST, default=host): str,
            probatio.Required(CONF_API_KEY): API_KEY_SELECTOR,
            probatio.Optional(CONF_PORT, default=port): int,
            probatio.Optional(CONF_VERIFY_SSL, default=verify_ssl): bool,
        }
    )


@contextmanager
def _catch_unifi_api_flow_errors(
    errors: dict[str, str], auth_error_field: str = "base"
) -> Iterator[None]:
    """Map UniFi API exceptions to config flow form errors.

    `get_unifi_api` maps what its first request raises; the site request
    that follows it raises aiounifi's own exceptions, mapped here the same
    way.
    """
    try:
        yield
    except AuthenticationRequired, aiounifi.Unauthorized, aiounifi.LoginRequired:
        errors[auth_error_field] = "faulty_credentials"
    except CannotConnect, TimeoutError, aiounifi.AiounifiException:
        errors["base"] = "service_unavailable"
