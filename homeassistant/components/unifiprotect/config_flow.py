"""Config Flow to configure UniFi Protect Integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from pathlib import Path
from typing import Any

from aiohttp import CookieJar
from pyunifiprotect import ProtectApiClient
from pyunifiprotect.data import NVR
from pyunifiprotect.exceptions import ClientError, NotAuthorized
from unifi_discovery import async_console_is_alive
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp, ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.loader import async_get_integration
from homeassistant.util.network import is_ip_address

from .const import (
    CONF_ALL_UPDATES,
    CONF_ALLOW_EA,
    CONF_DISABLE_RTSP,
    CONF_MAX_MEDIA,
    CONF_OVERRIDE_CHOST,
    DEFAULT_MAX_MEDIA,
    DEFAULT_PORT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_REQUIRED_PROTECT_V,
    OUTDATED_LOG_MESSAGE,
)
from .data import async_last_update_was_successful
from .discovery import async_start_discovery
from .utils import _async_resolve, _async_short_mac, _async_unifi_mac_from_hass

_LOGGER = logging.getLogger(__name__)

ENTRY_FAILURE_STATES = (
    config_entries.ConfigEntryState.SETUP_ERROR,
    config_entries.ConfigEntryState.SETUP_RETRY,
)


async def async_local_user_documentation_url(hass: HomeAssistant) -> str:
    """Get the documentation url for creating a local user."""
    integration = await async_get_integration(hass, DOMAIN)
    return f"{integration.documentation}#local-user"


def _host_is_direct_connect(host: str) -> bool:
    """Check if a host is a unifi direct connect domain."""
    return host.endswith(".ui.direct")


async def _async_console_is_offline(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
) -> bool:
    """Check if a console is offline.

    We define offline by the config entry
    is in a failure/retry state or the updates
    are failing and the console is unreachable
    since protect may be updating.
    """
    return bool(
        entry.state in ENTRY_FAILURE_STATES
        or not async_last_update_was_successful(hass, entry)
    ) and not await async_console_is_alive(
        async_get_clientsession(hass, verify_ssl=False), entry.data[CONF_HOST]
    )


class ProtectFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UniFi Protect config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Init the config flow."""
        super().__init__()
        self.entry: config_entries.ConfigEntry | None = None
        self._discovered_device: dict[str, str] = {}

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        _LOGGER.debug("Starting discovery via: %s", discovery_info)
        return await self._async_discovery_handoff()

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a discovered UniFi device."""
        _LOGGER.debug("Starting discovery via: %s", discovery_info)
        return await self._async_discovery_handoff()

    async def _async_discovery_handoff(self) -> FlowResult:
        """Ensure discovery is active."""
        # Discovery requires an additional check so we use
        # SSDP and DHCP to tell us to start it so it only
        # runs on networks where unifi devices are present.
        async_start_discovery(self.hass)
        return self.async_abort(reason="discovery_started")

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle integration discovery."""
        self._discovered_device = discovery_info
        mac = _async_unifi_mac_from_hass(discovery_info["hw_addr"])
        await self.async_set_unique_id(mac)
        source_ip = discovery_info["source_ip"]
        direct_connect_domain = discovery_info["direct_connect_domain"]
        for entry in self._async_current_entries():
            if entry.source == config_entries.SOURCE_IGNORE:
                if entry.unique_id == mac:
                    return self.async_abort(reason="already_configured")
                continue
            entry_host = entry.data[CONF_HOST]
            entry_has_direct_connect = _host_is_direct_connect(entry_host)
            if entry.unique_id == mac:
                new_host = None
                if (
                    entry_has_direct_connect
                    and direct_connect_domain
                    and entry_host != direct_connect_domain
                ):
                    new_host = direct_connect_domain
                elif (
                    not entry_has_direct_connect
                    and is_ip_address(entry_host)
                    and entry_host != source_ip
                    and await _async_console_is_offline(self.hass, entry)
                ):
                    new_host = source_ip
                if new_host:
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_HOST: new_host}
                    )
                return self.async_abort(reason="already_configured")
            if entry_host in (direct_connect_domain, source_ip) or (
                entry_has_direct_connect
                and (ip := await _async_resolve(self.hass, entry_host))
                and ip == source_ip
            ):
                return self.async_abort(reason="already_configured")
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}
        discovery_info = self._discovered_device
        if user_input is not None:
            user_input[CONF_PORT] = DEFAULT_PORT
            nvr_data = None
            if discovery_info["direct_connect_domain"]:
                user_input[CONF_HOST] = discovery_info["direct_connect_domain"]
                user_input[CONF_VERIFY_SSL] = True
                nvr_data, errors = await self._async_get_nvr_data(user_input)
            if not nvr_data or errors:
                user_input[CONF_HOST] = discovery_info["source_ip"]
                user_input[CONF_VERIFY_SSL] = False
                nvr_data, errors = await self._async_get_nvr_data(user_input)
            if nvr_data and not errors:
                return self._async_create_entry(nvr_data.display_name, user_input)

        placeholders = {
            "name": discovery_info["hostname"]
            or discovery_info["platform"]
            or f"NVR {_async_short_mac(discovery_info['hw_addr'])}",
            "ip_address": discovery_info["source_ip"],
        }
        self.context["title_placeholders"] = placeholders
        user_input = user_input or {}
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                **placeholders,
                "local_user_documentation_url": await async_local_user_documentation_url(
                    self.hass
                ),
            },
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    @callback
    def _async_create_entry(self, title: str, data: dict[str, Any]) -> FlowResult:
        return self.async_create_entry(
            title=title,
            data={**data, CONF_ID: title},
            options={
                CONF_DISABLE_RTSP: False,
                CONF_ALL_UPDATES: False,
                CONF_OVERRIDE_CHOST: False,
                CONF_MAX_MEDIA: DEFAULT_MAX_MEDIA,
                CONF_ALLOW_EA: False,
            },
        )

    async def _async_get_nvr_data(
        self,
        user_input: dict[str, Any],
    ) -> tuple[NVR | None, dict[str, str]]:
        session = async_create_clientsession(
            self.hass, cookie_jar=CookieJar(unsafe=True)
        )

        host = user_input[CONF_HOST]
        port = user_input.get(CONF_PORT, DEFAULT_PORT)
        verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

        protect = ProtectApiClient(
            session=session,
            host=host,
            port=port,
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            verify_ssl=verify_ssl,
            cache_dir=Path(self.hass.config.path(STORAGE_DIR, "unifiprotect_cache")),
        )

        errors = {}
        nvr_data = None
        try:
            nvr_data = await protect.get_nvr()
        except NotAuthorized as ex:
            _LOGGER.debug(ex)
            errors[CONF_PASSWORD] = "invalid_auth"
        except ClientError as ex:
            _LOGGER.debug(ex)
            errors["base"] = "cannot_connect"
        else:
            if nvr_data.version < MIN_REQUIRED_PROTECT_V:
                _LOGGER.debug(
                    OUTDATED_LOG_MESSAGE,
                    nvr_data.version,
                    MIN_REQUIRED_PROTECT_V,
                )
                errors["base"] = "protect_version"

        return nvr_data, errors

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth."""
        errors: dict[str, str] = {}
        assert self.entry is not None

        # prepopulate fields
        form_data = {**self.entry.data}
        if user_input is not None:
            form_data.update(user_input)

            # validate login data
            _, errors = await self._async_get_nvr_data(form_data)
            if not errors:
                self.hass.config_entries.async_update_entry(self.entry, data=form_data)
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        self.context["title_placeholders"] = {
            "name": self.entry.title,
            "ip_address": self.entry.data[CONF_HOST],
        }
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=form_data.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            nvr_data, errors = await self._async_get_nvr_data(user_input)

            if nvr_data and not errors:
                await self.async_set_unique_id(nvr_data.mac)
                self._abort_if_unique_id_configured()

                return self._async_create_entry(nvr_data.display_name, user_input)

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "local_user_documentation_url": await async_local_user_documentation_url(
                    self.hass
                )
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    ): bool,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DISABLE_RTSP,
                        default=self.config_entry.options.get(CONF_DISABLE_RTSP, False),
                    ): bool,
                    vol.Optional(
                        CONF_ALL_UPDATES,
                        default=self.config_entry.options.get(CONF_ALL_UPDATES, False),
                    ): bool,
                    vol.Optional(
                        CONF_OVERRIDE_CHOST,
                        default=self.config_entry.options.get(
                            CONF_OVERRIDE_CHOST, False
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_MAX_MEDIA,
                        default=self.config_entry.options.get(
                            CONF_MAX_MEDIA, DEFAULT_MAX_MEDIA
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=100, max=10000)),
                    vol.Optional(
                        CONF_ALLOW_EA,
                        default=self.config_entry.options.get(CONF_ALLOW_EA, False),
                    ): bool,
                }
            ),
        )
