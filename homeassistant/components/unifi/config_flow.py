"""Config flow for UniFi Network integration.

Provides user initiated configuration flow.
Discovery of UniFi Network instances through unifi_discovery.
Reauthentication when issue with credentials are reported.
Configuration of options through options flow.
"""

import asyncio
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import json
import operator
import socket
from types import MappingProxyType
from typing import Any, NamedTuple, override

import aiounifi
from aiounifi.interfaces.sites import Sites
import probatio

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, SectionConfig, section
from homeassistant.helpers import config_validation as cv
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
    CONNECTION_MODE_API_KEY_ONLY,
    DEFAULT_DPI_RESTRICTIONS,
    DOMAIN,
    LOGGER,
    NETWORK_MIN_DETECTION_TIME,
)
from .errors import (
    AuthenticationRequired,
    CannotConnect,
    MfaRequired,
    NetworkApiUnavailable,
)
from .hub import UnifiHub, async_move_site_devices, get_unifi_api, site_ids_moved
from .hub.config import entry_is_api_key_only

DEFAULT_HOST = "unifi"
DEFAULT_PORT = 443
DEFAULT_SITE_ID = "default"
DEFAULT_VERIFY_SSL = False
SITE_REQUEST_TIMEOUT = 10

API_KEY_DOCUMENTATION_URL = "https://www.home-assistant.io/integrations/unifi/#api-key"


class SiteChoice(NamedTuple):
    """A site to set up, by its short name and display name."""

    name: str
    title: str


class UnifiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a UniFi Network config flow."""

    VERSION = 1

    sites: dict[str, SiteChoice]

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
        """Let the user pick how to connect: a local user or an API key."""
        return self.async_show_menu(step_id="user", menu_options=["full", "api_key"])

    async def async_step_full(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect with a local user."""
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
            data_schema = self._build_form_schema(
                host=await self._async_default_host(),
                verify_ssl=self.config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            )

        return self.async_show_form(
            step_id="full",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect with only an API key of the Integration API."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.config = _api_key_config_from_input(user_input)
            data_schema = self._build_api_key_schema(
                self.config[CONF_HOST],
                self.config[CONF_PORT],
                self.config[CONF_VERIFY_SSL],
            )

            with _catch_unifi_api_flow_errors(errors):
                self.sites = await self._async_update_sites(self.config)
                return await self.async_step_site()
        else:
            data_schema = self._build_api_key_schema(
                host=await self._async_default_host(),
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

    async def async_step_site(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select site to control."""
        if user_input is not None:
            unique_id = user_input[CONF_SITE_ID]
            site = self.sites[unique_id]
            self.config[CONF_SITE_ID] = site.name

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            # The other API can key the same site by ObjectId instead of UUID
            for entry in self._async_current_entries(include_ignore=False):
                if (
                    entry.data.get(CONF_HOST) == self.config[CONF_HOST]
                    and entry.data.get(CONF_PORT) == self.config[CONF_PORT]
                    and entry.data.get(CONF_SITE_ID) == site.name
                    and entry.unique_id is not None
                    and site_ids_moved(entry.unique_id, unique_id)
                ):
                    return self.async_abort(reason="already_configured")

            return self.async_create_entry(title=site.title, data=self.config)

        if len(self.sites) == 1:
            return await self.async_step_site({CONF_SITE_ID: next(iter(self.sites))})

        site_names = {site_id: site.title for site_id, site in self.sites.items()}
        return self.async_show_form(
            step_id="site",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_SITE_ID): probatio.In(site_names)}
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Renew the credentials of the entry's mode."""
        reauth_entry = self._get_reauth_entry()
        self.context["title_placeholders"] = {
            "host": reauth_entry.data[CONF_HOST],
            "name": reauth_entry.title,
        }

        if entry_is_api_key_only(entry_data):
            return await self.async_step_reauth_api_key()
        return await self.async_step_reconfigure_full()

    async def async_step_reauth_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Renew the API key."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {**reauth_entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}
            with _catch_unifi_api_flow_errors(errors):
                # The info endpoint can accept a key the sites endpoint rejects
                await self._async_update_sites(data)
                return self._async_store_entry(reauth_entry, data)

        return self.async_show_form(
            step_id="reauth_api_key",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
            ),
            errors=errors,
            description_placeholders={
                "api_key_documentation_url": API_KEY_DOCUMENTATION_URL,
                "host": reauth_entry.data[CONF_HOST],
                "name": reauth_entry.title,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how to connect: a local user or an API key."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["reconfigure_full", "reconfigure_api_key"],
        )

    async def async_step_reconfigure_full(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect with a local user, a stored API key is kept."""
        config_entry = self._get_reauth_or_reconfigure_entry()
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
                return self._async_update_entry(config_entry, config_data, sites)
        else:
            data_schema = self._build_form_schema(
                config_entry.data[CONF_HOST],
                config_entry.data.get(CONF_USERNAME, ""),
                config_entry.data[CONF_PORT],
                config_entry.data[CONF_VERIFY_SSL],
            )

        return self.async_show_form(
            step_id="reconfigure_full",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect with only an API key, stored local user credentials are kept."""
        config_entry = self._get_reconfigure_entry()
        stored_api_key = config_entry.data.get(CONF_API_KEY)
        errors: dict[str, str] = {}

        if user_input is not None:
            config_data = _api_key_config_from_input(
                {
                    **user_input,
                    CONF_API_KEY: user_input.get(CONF_API_KEY) or stored_api_key,
                }
            )
            data_schema = self._build_api_key_schema(
                config_data[CONF_HOST],
                config_data[CONF_PORT],
                config_data[CONF_VERIFY_SSL],
                api_key_optional=stored_api_key is not None,
            )

            with _catch_unifi_api_flow_errors(errors):
                sites = await self._async_update_sites(config_data)
                return self._async_update_entry(config_entry, config_data, sites)
        else:
            data_schema = self._build_api_key_schema(
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_PORT],
                config_entry.data[CONF_VERIFY_SSL],
                api_key_optional=stored_api_key is not None,
            )

        return self.async_show_form(
            step_id="reconfigure_api_key",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "api_key_documentation_url": API_KEY_DOCUMENTATION_URL
            },
        )

    @callback
    def _async_update_entry(
        self,
        config_entry: UnifiConfigEntry,
        config_data: dict[str, Any],
        sites: dict[str, SiteChoice],
    ) -> ConfigFlowResult:
        """Store validated connection data and the site it resolves to."""
        old_id = config_entry.unique_id
        assert old_id is not None
        unique_id: str | None = old_id
        if unique_id not in sites:
            unique_id = self._async_match_moved_site(
                config_entry, old_id, config_data, sites
            )
        if unique_id is None:
            raise AbortFlow("unknown_site_id")
        if unique_id != old_id:
            async_move_site_devices(self.hass, config_entry.entry_id, old_id, unique_id)

        # Credentials of the other mode are kept, so switching back is lossless
        data = {**config_entry.data, **config_data, CONF_SITE_ID: sites[unique_id].name}
        if not entry_is_api_key_only(config_data):
            data.pop(CONF_CONNECTION_MODE, None)

        return self._async_store_entry(config_entry, data, unique_id)

    @callback
    def _async_store_entry(
        self,
        config_entry: UnifiConfigEntry,
        data: dict[str, Any],
        unique_id: str | None = None,
    ) -> ConfigFlowResult:
        """Update the entry and reload it, through the update listener when loaded."""
        unique_id = unique_id or config_entry.unique_id
        if config_entry.update_listeners:
            # The update listener reloads an entry when its data changes
            if data == config_entry.data:
                self.hass.config_entries.async_schedule_reload(config_entry.entry_id)
            return self.async_update_and_abort(
                config_entry, unique_id=unique_id, data=data
            )
        return self.async_update_reload_and_abort(
            config_entry, unique_id=unique_id, data=data
        )

    @callback
    def _async_match_moved_site(
        self,
        config_entry: UnifiConfigEntry,
        old_id: str,
        config_data: dict[str, Any],
        sites: dict[str, SiteChoice],
    ) -> str | None:
        """Find the site the other API keys differently, only on the same console."""
        if (
            config_data[CONF_HOST] != config_entry.data[CONF_HOST]
            or config_data[CONF_PORT] != config_entry.data[CONF_PORT]
        ):
            return None
        unique_id = next(
            (
                site_id
                for site_id, site in sites.items()
                if site.name == config_entry.data[CONF_SITE_ID]
                and site_ids_moved(old_id, site_id)
            ),
            None,
        )
        if (
            unique_id is not None
            and self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            )
        ):
            raise AbortFlow("already_configured")
        return unique_id

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

        # Entries are keyed by site and a console may announce no address.
        # Not the device registry: it also holds clients, which a console can be.
        loaded_entries: list[UnifiConfigEntry] = (
            self.hass.config_entries.async_loaded_entries(DOMAIN)
        )
        if any(
            mac_address in entry.runtime_data.api.devices
            or mac_address in entry.runtime_data.api.network.devices
            for entry in loaded_entries
        ):
            return self.async_abort(reason="already_configured")

        self.context["title_placeholders"] = {
            "name": (
                discovery_info.get("name")
                or discovery_info.get("hostname")
                or discovery_info.get("product_name")
                or "UniFi Network"
            ),
            "host": source_ip,
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
        """Build the form of a local user."""
        return probatio.Schema(
            {
                probatio.Required(CONF_HOST, default=host): str,
                probatio.Required(CONF_USERNAME, default=username): str,
                probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                probatio.Optional(CONF_PORT, default=port): int,
                probatio.Optional(CONF_VERIFY_SSL, default=verify_ssl): bool,
            }
        )

    def _build_api_key_schema(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        verify_ssl: bool = DEFAULT_VERIFY_SSL,
        *,
        api_key_optional: bool = False,
    ) -> probatio.Schema:
        """Build the form of an API key, an optional key keeps the stored one."""
        api_key_marker = probatio.Optional if api_key_optional else probatio.Required
        return probatio.Schema(
            {
                probatio.Required(CONF_HOST, default=host): str,
                api_key_marker(probatio.Secret(CONF_API_KEY)): str,
                probatio.Optional(CONF_PORT, default=port): int,
                probatio.Optional(CONF_VERIFY_SSL, default=verify_ssl): bool,
            }
        )

    async def _async_default_host(self) -> str:
        """Return the discovered host, or the address the name unifi has."""
        host: str | None = self.config.get(CONF_HOST)
        if host:
            return host
        return await _async_discover_unifi(self.hass) or DEFAULT_HOST

    async def _async_update_sites(
        self, data: Mapping[str, Any]
    ) -> dict[str, SiteChoice]:
        """Get updated sites through the API of the connection mode."""
        hub = await get_unifi_api(self.hass, MappingProxyType(data))
        sites = hub.network.sites if entry_is_api_key_only(data) else hub.sites
        try:
            async with asyncio.timeout(SITE_REQUEST_TIMEOUT):
                await sites.update()
        except (
            aiounifi.Forbidden,
            aiounifi.LoginRequired,
            aiounifi.NoPermission,
            aiounifi.Unauthorized,
        ) as err:
            LOGGER.warning(
                "UniFi Network at %s rejected the site request: %s",
                data[CONF_HOST],
                type(err).__name__,
            )
            raise AuthenticationRequired from err
        # aiounifi 97 does not wrap JSON decode errors, newer releases do
        except (TimeoutError, json.JSONDecodeError, aiounifi.AiounifiException) as err:
            LOGGER.warning(
                "Error fetching sites from UniFi Network at %s: %r",
                data[CONF_HOST],
                err,
            )
            raise CannotConnect from err
        if not sites.values():
            # aiounifi 97 returns no sites when the console answers with HTML,
            # as it does while the Network application is missing or starting
            LOGGER.warning("No sites found on UniFi Network at %s", data[CONF_HOST])
            raise CannotConnect
        if isinstance(sites, Sites):
            return {
                site.site_id: SiteChoice(site.name, site.description)
                for site in sites.values()
            }
        return {
            site.site_id: SiteChoice(site.internal_reference, site.name)
            for site in sites.values()
        }

    @callback
    def _get_reauth_or_reconfigure_entry(self) -> UnifiConfigEntry:
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
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="integration_not_setup")

        self.hub = self.config_entry.runtime_data
        self.options[CONF_BLOCK_CLIENT] = self.hub.config.option_block_clients

        if user_input is not None:
            more_options = user_input.pop(CONF_MORE_OPTIONS, {})
            user_input.update(more_options)
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        if self.hub.config.api_key_only:
            return self._async_show_network_api_form()

        clients_to_block = {}
        for client in self.hub.api.clients.values():
            clients_to_block[client.mac] = (
                f"{client.name or client.hostname} ({client.mac})"
            )

        selected_clients_to_block = [
            client
            for client in self.options.get(CONF_BLOCK_CLIENT, [])
            if client in clients_to_block
        ]

        clients = {
            client.mac: f"{client.name or client.hostname} ({client.mac})"
            for client in self.hub.api.clients.values()
        }
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

    @callback
    def _async_show_network_api_form(self) -> ConfigFlowResult:
        """Show the options the Integration API supports."""
        config = self.hub.config
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_TRACK_CLIENTS, default=config.option_track_clients
                    ): bool,
                    probatio.Optional(
                        CONF_TRACK_DEVICES, default=config.option_track_devices
                    ): bool,
                    probatio.Required(CONF_MORE_OPTIONS): section(
                        probatio.Schema(
                            {
                                probatio.Optional(
                                    CONF_TRACK_WIRED_CLIENTS,
                                    default=config.option_track_wired_clients,
                                ): bool,
                                probatio.Optional(
                                    CONF_DETECTION_TIME,
                                    default=max(
                                        int(
                                            config.option_detection_time.total_seconds()
                                        ),
                                        NETWORK_MIN_DETECTION_TIME,
                                    ),
                                ): probatio.All(
                                    int,
                                    probatio.Range(min=NETWORK_MIN_DETECTION_TIME),
                                ),
                                probatio.Optional(
                                    CONF_IGNORE_LOCAL_MAC,
                                    default=config.option_ignore_local_mac,
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


def _api_key_config_from_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build config entry data of an API key from user input."""
    return {
        CONF_HOST: user_input[CONF_HOST],
        CONF_API_KEY: user_input[CONF_API_KEY],
        CONF_PORT: user_input.get(CONF_PORT),
        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
        CONF_SITE_ID: DEFAULT_SITE_ID,
        CONF_CONNECTION_MODE: CONNECTION_MODE_API_KEY_ONLY,
    }


def _config_from_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build config entry data from user input."""
    return {
        CONF_HOST: user_input[CONF_HOST],
        CONF_USERNAME: user_input[CONF_USERNAME],
        CONF_PASSWORD: user_input[CONF_PASSWORD],
        CONF_PORT: user_input.get(CONF_PORT),
        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
        CONF_SITE_ID: DEFAULT_SITE_ID,
    }


@contextmanager
def _catch_unifi_api_flow_errors(errors: dict[str, str]) -> Iterator[None]:
    """Map UniFi API exceptions to config flow form errors."""
    try:
        yield
    except MfaRequired:
        errors["base"] = "mfa_required"
    except AuthenticationRequired:
        errors["base"] = "faulty_credentials"
    except NetworkApiUnavailable:
        errors["base"] = "network_api_unavailable"
    except CannotConnect:
        errors["base"] = "service_unavailable"
