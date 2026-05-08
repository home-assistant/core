"""Config flow for UniFi Network integration.

Provides user initiated configuration flow.
Discovery of UniFi Network instances through unifi_discovery.
Reauthentication when issue with credentials are reported.
Configuration of options through options flow.
"""

from collections.abc import Mapping
import operator
import socket
from types import MappingProxyType
from typing import Any

from aiounifi.interfaces.sites import Sites
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import DiscoveryInfoType

from . import UnifiConfigEntry
from .const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CLIENT_SOURCE,
    CONF_DETECTION_TIME,
    CONF_DPI_RESTRICTIONS,
    CONF_IGNORE_WIRED_BUG,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    DEFAULT_DPI_RESTRICTIONS,
    DOMAIN,
)
from .errors import AuthenticationRequired, CannotConnect
from .hub import UnifiHub, get_unifi_api

DEFAULT_PORT = 443
DEFAULT_SITE_ID = "default"
DEFAULT_VERIFY_SSL = False
UNIQUE_ID_SEPARATOR = "::"


@callback
def _normalize_host(host: str) -> str:
    """Normalize a controller host for matching and fallback IDs."""
    return host.strip().lower()


@callback
def _normalize_controller_key(controller_key: str | None, host: str) -> str:
    """Return the preferred stable controller key, falling back to host."""
    if controller_key:
        return controller_key.strip().lower()
    return _normalize_host(host)


@callback
def _make_unique_id(controller_key: str | None, host: str, site_id: str) -> str:
    """Build a config-entry unique ID for one controller + one site."""
    return (
        f"{_normalize_controller_key(controller_key, host)}"
        f"{UNIQUE_ID_SEPARATOR}{site_id}"
    )


@callback
def _extract_site_id(unique_id: str | None) -> str | None:
    """Return the raw site_id from a legacy or compound unique ID."""
    if not unique_id:
        return None
    if UNIQUE_ID_SEPARATOR not in unique_id:
        return unique_id
    return unique_id.rsplit(UNIQUE_ID_SEPARATOR, 1)[-1]


@callback
def _extract_controller_key(unique_id: str | None) -> str | None:
    """Return the controller key from a compound unique ID if present."""
    if not unique_id or UNIQUE_ID_SEPARATOR not in unique_id:
        return None
    return unique_id.split(UNIQUE_ID_SEPARATOR, 1)[0]


@callback
def _entry_matches_target(
    *,
    entry_unique_id: str | None,
    entry_host: str | None,
    entry_site_name: str | None,
    target_controller_key: str | None,
    target_host: str,
    target_site_id: str,
    target_site_name: str,
) -> bool:
    """Return True if a config entry matches the same controller + site."""
    current_site_id = _extract_site_id(entry_unique_id)
    if current_site_id not in (target_site_id, None):
        return False

    target_normalized_host = _normalize_host(target_host)
    target_normalized_key = _normalize_controller_key(target_controller_key, target_host)

    current_controller_key = _extract_controller_key(entry_unique_id)
    if current_controller_key is not None:
        return current_controller_key == target_normalized_key

    current_host = _normalize_host(entry_host or "")
    current_site_name = entry_site_name or ""
    return current_host == target_normalized_host and current_site_name in (
        target_site_name,
        target_site_id,
    )


class UnifiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a UniFi Network config flow."""

    VERSION = 1

    sites: Sites

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: UnifiConfigEntry,
    ) -> UnifiOptionsFlowHandler:
        """Get the options flow for this handler."""
        return UnifiOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize the UniFi Network flow."""
        self.config: dict[str, Any] = {}
        self.controller_key: str | None = None
        self.reauth_schema: dict[vol.Marker, Any] = {}

    @callback
    def _find_matching_entry(self, host: str, site_id: str, site_name: str):
        """Find an already-configured entry for the same controller + site."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.domain != DOMAIN:
                continue
            if _entry_matches_target(
                entry_unique_id=entry.unique_id,
                entry_host=str(entry.data.get(CONF_HOST, "")),
                entry_site_name=str(entry.data.get(CONF_SITE_ID, "")),
                target_controller_key=self.controller_key,
                target_host=host,
                target_site_id=site_id,
                target_site_name=site_name,
            ):
                return entry
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self.config = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_PORT: user_input.get(CONF_PORT),
                CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
                CONF_SITE_ID: DEFAULT_SITE_ID,
            }

            try:
                hub = await get_unifi_api(self.hass, MappingProxyType(self.config))
                await hub.sites.update()
                self.sites = hub.sites
                await hub.system_information.update()
                controller_info = next(iter(hub.system_information.values()), None)
                self.controller_key = (
                    controller_info.anonymous_controller_id
                    if controller_info is not None
                    else None
                )

            except AuthenticationRequired:
                errors["base"] = "faulty_credentials"

            except CannotConnect:
                errors["base"] = "service_unavailable"

            else:
                if (
                    self.source == SOURCE_REAUTH
                    and (
                        (reauth_unique_id := self._get_reauth_entry().unique_id)
                        is not None
                    )
                    and (reauth_site_id := _extract_site_id(reauth_unique_id))
                    is not None
                    and reauth_site_id in self.sites
                ):
                    return await self.async_step_site({CONF_SITE_ID: reauth_site_id})

                return await self.async_step_site()

        if not (host := self.config.get(CONF_HOST, "")) and await _async_discover_unifi(
            self.hass
        ):
            host = "unifi"

        data = self.reauth_schema or {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(
                CONF_PORT, default=self.config.get(CONF_PORT, DEFAULT_PORT)
            ): int,
            vol.Optional(
                CONF_VERIFY_SSL,
                default=self.config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): bool,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data),
            errors=errors,
        )

    async def async_step_site(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select site to control."""
        if user_input is not None:
            site_id = user_input[CONF_SITE_ID]
            site = self.sites[site_id]
            host = str(self.config[CONF_HOST])
            unique_id = _make_unique_id(self.controller_key, host, site_id)
            self.config[CONF_SITE_ID] = site.name

            config_entry = None
            abort_reason = "configuration_updated"

            if self.source == SOURCE_REAUTH:
                config_entry = self._get_reauth_entry()
                abort_reason = "reauth_successful"
            else:
                config_entry = await self.async_set_unique_id(unique_id)
                if config_entry is None:
                    config_entry = self._find_matching_entry(host, site_id, site.name)

            if config_entry:
                if config_entry.unique_id != unique_id:
                    self.hass.config_entries.async_update_entry(
                        config_entry, unique_id=unique_id
                    )

                if (
                    config_entry.state is ConfigEntryState.LOADED
                    and (hub := config_entry.runtime_data)
                    and hub.available
                ):
                    return self.async_abort(reason="already_configured")

                return self.async_update_and_abort(
                    config_entry, data=self.config, reason=abort_reason
                )

            await self.async_set_unique_id(unique_id)
            site_nice_name = f"{host} ({site.description})"
            return self.async_create_entry(title=site_nice_name, data=self.config)

        if len(self.sites.values()) == 1:
            return await self.async_step_site({CONF_SITE_ID: next(iter(self.sites))})

        site_names = {site.site_id: site.description for site in self.sites.values()}
        return self.async_show_form(
            step_id="site",
            data_schema=vol.Schema({vol.Required(CONF_SITE_ID): vol.In(site_names)}),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger a reauthentication flow."""
        reauth_entry = self._get_reauth_entry()

        self.context["title_placeholders"] = {
            CONF_HOST: reauth_entry.data[CONF_HOST],
            CONF_SITE_ID: reauth_entry.title,
        }

        self.reauth_schema = {
            vol.Required(CONF_HOST, default=reauth_entry.data[CONF_HOST]): str,
            vol.Required(CONF_USERNAME, default=reauth_entry.data[CONF_USERNAME]): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=reauth_entry.data[CONF_PORT]): int,
            vol.Required(
                CONF_VERIFY_SSL, default=reauth_entry.data[CONF_VERIFY_SSL]
            ): bool,
        }

        return await self.async_step_user()

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

        for entry in self._async_current_entries(include_ignore=False):
            if entry.data.get(CONF_HOST) in (source_ip, direct_connect_domain):
                return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(updates=self.config, reload_on_update=False)

        self.context["title_placeholders"] = {
            CONF_HOST: host,
            CONF_SITE_ID: DEFAULT_SITE_ID,
        }
        self.context["configuration_url"] = f"https://{host}"

        return await self.async_step_user()


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

        if self.show_advanced_options:
            return await self.async_step_configure_entity_sources()

        return await self.async_step_simple_options()

    async def async_step_simple_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """For users without advanced settings enabled."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        clients_to_block = {}

        for client in self.hub.api.clients.values():
            clients_to_block[client.mac] = (
                f"{client.name or client.hostname} ({client.mac})"
            )

        return self.async_show_form(
            step_id="simple_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TRACK_CLIENTS,
                        default=self.hub.config.option_track_clients,
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_DEVICES,
                        default=self.hub.config.option_track_devices,
                    ): bool,
                    vol.Optional(
                        CONF_BLOCK_CLIENT, default=self.options[CONF_BLOCK_CLIENT]
                    ): cv.multi_select(clients_to_block),
                }
            ),
            last_step=True,
        )

    async def async_step_configure_entity_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select sources for entities."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_device_tracker()

        clients = {
            client.mac: f"{client.name or client.hostname} ({client.mac})"
            for client in self.hub.api.clients.values()
        }
        clients |= {
            mac: f"Unknown ({mac})"
            for mac in self.options.get(CONF_CLIENT_SOURCE, [])
            if mac not in clients
        }

        return self.async_show_form(
            step_id="configure_entity_sources",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CLIENT_SOURCE,
                        default=self.options.get(CONF_CLIENT_SOURCE, []),
                    ): cv.multi_select(
                        dict(sorted(clients.items(), key=operator.itemgetter(1)))
                    ),
                }
            ),
            last_step=False,
        )

    async def async_step_device_tracker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the device tracker options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_client_control()

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
            step_id="device_tracker",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TRACK_CLIENTS,
                        default=self.hub.config.option_track_clients,
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_WIRED_CLIENTS,
                        default=self.hub.config.option_track_wired_clients,
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_DEVICES,
                        default=self.hub.config.option_track_devices,
                    ): bool,
                    vol.Optional(
                        CONF_SSID_FILTER, default=selected_ssids_to_filter
                    ): cv.multi_select(ssid_filter),
                    vol.Optional(
                        CONF_DETECTION_TIME,
                        default=int(
                            self.hub.config.option_detection_time.total_seconds()
                        ),
                    ): int,
                    vol.Optional(
                        CONF_IGNORE_WIRED_BUG,
                        default=self.hub.config.option_ignore_wired_bug,
                    ): bool,
                }
            ),
            last_step=False,
        )

    async def async_step_client_control(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage configuration of network access controlled clients."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_statistics_sensors()

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

        return self.async_show_form(
            step_id="client_control",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BLOCK_CLIENT, default=selected_clients_to_block
                    ): cv.multi_select(clients_to_block),
                    vol.Optional(
                        CONF_DPI_RESTRICTIONS,
                        default=self.options.get(
                            CONF_DPI_RESTRICTIONS, DEFAULT_DPI_RESTRICTIONS
                        ),
                    ): bool,
                }
            ),
            last_step=False,
        )

    async def async_step_statistics_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                        default=self.hub.config.option_allow_bandwidth_sensors,
                    ): bool,
                    vol.Optional(
                        CONF_ALLOW_UPTIME_SENSORS,
                        default=self.hub.config.option_allow_uptime_sensors,
                    ): bool,
                }
            ),
            last_step=True,
        )

    async def _update_options(self) -> ConfigFlowResult:
        """Update config entry options."""
        return self.async_create_entry(title="", data=self.options)


async def _async_discover_unifi(hass: HomeAssistant) -> str | None:
    """Discover UniFi Network address."""
    try:
        return await hass.async_add_executor_job(socket.gethostbyname, "unifi")
    except socket.gaierror:
        return None
