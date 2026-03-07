"""Config Flow to configure UniFi Protect Integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from pathlib import Path
from typing import Any

from aiohttp import CookieJar
from uiprotect import ProtectApiClient
from uiprotect.data import NVR
from uiprotect.exceptions import ClientError, NotAuthorized
from unifi_discovery import async_console_is_alive
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.loader import async_get_integration
from homeassistant.util.network import is_ip_address

from .const import (
    CONF_ALL_UPDATES,
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
from .data import UFPConfigEntry, async_last_update_was_successful
from .discovery import async_start_discovery
from .utils import (
    _async_resolve,
    _async_short_mac,
    _async_unifi_mac_from_hass,
    async_create_api_client,
)

_LOGGER = logging.getLogger(__name__)


def _filter_empty_credentials(user_input: dict[str, Any]) -> dict[str, Any]:
    """Filter out empty credential fields to preserve existing values."""
    return {k: v for k, v in user_input.items() if v not in (None, "")}


def _normalize_port(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure port is stored as int (NumberSelector returns float)."""
    return {**data, CONF_PORT: int(data.get(CONF_PORT, DEFAULT_PORT))}


def _build_data_without_credentials(entry_data: Mapping[str, Any]) -> dict[str, Any]:
    """Build form data from existing config entry, excluding sensitive credentials."""
    return {
        CONF_HOST: entry_data[CONF_HOST],
        CONF_PORT: entry_data[CONF_PORT],
        CONF_VERIFY_SSL: entry_data[CONF_VERIFY_SSL],
        CONF_USERNAME: entry_data[CONF_USERNAME],
    }


async def _async_clear_session_if_credentials_changed(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    new_data: Mapping[str, Any],
) -> None:
    """Clear stored session if credentials have changed to force fresh authentication."""
    existing_data = entry.data
    if existing_data.get(CONF_USERNAME) != new_data.get(
        CONF_USERNAME
    ) or existing_data.get(CONF_PASSWORD) != new_data.get(CONF_PASSWORD):
        _LOGGER.debug("Credentials changed, clearing stored session")
        protect = async_create_api_client(hass, entry)
        try:
            await protect.clear_session()
        except Exception as ex:  # noqa: BLE001
            _LOGGER.debug("Failed to clear session, continuing anyway: %s", ex)


ENTRY_FAILURE_STATES = (
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
)

# Selectors for config flow form fields
_TEXT_SELECTOR = selector.TextSelector()
_PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)
_PORT_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        mode=selector.NumberSelectorMode.BOX, min=1, max=65535
    )
)
_BOOL_SELECTOR = selector.BooleanSelector()


def _build_schema(
    *,
    include_host: bool = True,
    include_connection: bool = True,
    credentials_optional: bool = False,
) -> vol.Schema:
    """Build a config flow schema.

    Args:
        include_host: Include host field (False when host comes from discovery).
        include_connection: Include port/verify_ssl fields.
        credentials_optional: Credentials optional (True to keep existing values).

    """
    req, opt = vol.Required, vol.Optional
    cred_key = opt if credentials_optional else req

    schema: dict[vol.Marker, selector.Selector] = {}
    if include_host:
        schema[req(CONF_HOST)] = _TEXT_SELECTOR
    if include_connection:
        schema[req(CONF_PORT, default=DEFAULT_PORT)] = _PORT_SELECTOR
        schema[req(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL)] = _BOOL_SELECTOR
    schema[req(CONF_USERNAME)] = _TEXT_SELECTOR
    schema[cred_key(CONF_PASSWORD)] = _PASSWORD_SELECTOR
    schema[cred_key(CONF_API_KEY)] = _PASSWORD_SELECTOR
    return vol.Schema(schema)


# Schemas for different flow contexts
# User flow: all fields required
CONFIG_SCHEMA = _build_schema()
# Reconfigure flow: keep existing credentials if not provided
RECONFIGURE_SCHEMA = _build_schema(credentials_optional=True)
# Discovery flow: host comes from discovery, user sets port/ssl
DISCOVERY_SCHEMA = _build_schema(include_host=False)
# Reauth flow: only credentials, connection settings preserved
REAUTH_SCHEMA = _build_schema(
    include_host=False, include_connection=False, credentials_optional=True
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
    entry: UFPConfigEntry,
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


class ProtectFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a UniFi Protect config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Init the config flow."""
        super().__init__()
        self._discovered_device: dict[str, str] = {}

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        _LOGGER.debug("Starting discovery via: %s", discovery_info)
        return await self._async_discovery_handoff()

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered UniFi device."""
        _LOGGER.debug("Starting discovery via: %s", discovery_info)
        return await self._async_discovery_handoff()

    async def _async_discovery_handoff(self) -> ConfigFlowResult:
        """Ensure discovery is active."""
        # Discovery requires an additional check so we use
        # SSDP and DHCP to tell us to start it so it only
        # runs on networks where unifi devices are present.
        async_start_discovery(self.hass)
        return self.async_abort(reason="discovery_started")

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        self._discovered_device = discovery_info
        mac = _async_unifi_mac_from_hass(discovery_info["hw_addr"])
        await self.async_set_unique_id(mac)
        source_ip = discovery_info["source_ip"]
        direct_connect_domain = discovery_info["direct_connect_domain"]
        for entry in self._async_current_entries():
            if entry.source == SOURCE_IGNORE:
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
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}
        discovery_info = self._discovered_device

        form_data = {
            CONF_HOST: discovery_info["direct_connect_domain"]
            or discovery_info["source_ip"],
            CONF_PORT: DEFAULT_PORT,
            CONF_VERIFY_SSL: bool(discovery_info["direct_connect_domain"]),
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
        }

        if user_input is not None:
            # Merge user input with discovery info
            merged_input = {**form_data, **user_input}
            nvr_data = None
            if discovery_info["direct_connect_domain"]:
                merged_input[CONF_HOST] = discovery_info["direct_connect_domain"]
                merged_input[CONF_VERIFY_SSL] = True
                nvr_data, errors = await self._async_get_nvr_data(merged_input)
            if not nvr_data or errors:
                merged_input[CONF_HOST] = discovery_info["source_ip"]
                merged_input[CONF_VERIFY_SSL] = False
                nvr_data, errors = await self._async_get_nvr_data(merged_input)
            if nvr_data and not errors:
                return self._async_create_entry(nvr_data.display_name, merged_input)
            # Preserve user input for form re-display, but keep discovery info
            form_data = {
                CONF_HOST: merged_input[CONF_HOST],
                CONF_PORT: merged_input[CONF_PORT],
                CONF_VERIFY_SSL: merged_input[CONF_VERIFY_SSL],
                CONF_USERNAME: user_input.get(CONF_USERNAME, ""),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
            }
            if CONF_API_KEY in user_input:
                form_data[CONF_API_KEY] = user_input[CONF_API_KEY]

        placeholders = {
            "name": discovery_info["hostname"]
            or discovery_info["platform"]
            or f"NVR {_async_short_mac(discovery_info['hw_addr'])}",
            "ip_address": discovery_info["source_ip"],
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                **placeholders,
                "local_user_documentation_url": await async_local_user_documentation_url(
                    self.hass
                ),
            },
            data_schema=self.add_suggested_values_to_schema(
                DISCOVERY_SCHEMA, form_data
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: UFPConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    @callback
    def _async_create_entry(self, title: str, data: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(
            title=title,
            data={**_normalize_port(data), CONF_ID: title},
            options={
                CONF_DISABLE_RTSP: False,
                CONF_ALL_UPDATES: False,
                CONF_OVERRIDE_CHOST: False,
                CONF_MAX_MEDIA: DEFAULT_MAX_MEDIA,
            },
        )

    async def _async_get_nvr_data(
        self,
        user_input: dict[str, Any],
    ) -> tuple[NVR | None, dict[str, str]]:
        session = async_create_clientsession(
            self.hass, cookie_jar=CookieJar(unsafe=True)
        )
        public_api_session = async_get_clientsession(self.hass)

        host = user_input[CONF_HOST]
        port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
        verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

        protect = ProtectApiClient(
            session=session,
            public_api_session=public_api_session,
            host=host,
            port=port,
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            api_key=user_input.get(CONF_API_KEY, ""),
            verify_ssl=verify_ssl,
            cache_dir=Path(self.hass.config.path(STORAGE_DIR, "unifiprotect")),
            config_dir=Path(self.hass.config.path(STORAGE_DIR, "unifiprotect")),
        )

        errors = {}
        nvr_data = None
        try:
            bootstrap = await protect.get_bootstrap()
            nvr_data = bootstrap.nvr
        except NotAuthorized as ex:
            _LOGGER.debug(ex)
            errors[CONF_PASSWORD] = "invalid_auth"
        except ClientError as ex:
            _LOGGER.error(ex)
            errors["base"] = "cannot_connect"
        else:
            if nvr_data.version < MIN_REQUIRED_PROTECT_V:
                _LOGGER.debug(
                    OUTDATED_LOG_MESSAGE,
                    nvr_data.version,
                    MIN_REQUIRED_PROTECT_V,
                )
                errors["base"] = "protect_version"

            auth_user = bootstrap.users.get(bootstrap.auth_user_id)
            if auth_user and auth_user.cloud_account:
                errors["base"] = "cloud_user"

        # Only validate API key if bootstrap succeeded
        if nvr_data and not errors:
            try:
                await protect.get_meta_info()
            except NotAuthorized as ex:
                _LOGGER.debug(ex)
                errors[CONF_API_KEY] = "invalid_auth"
            except ClientError as ex:
                _LOGGER.error(ex)
                errors["base"] = "cannot_connect"

        return nvr_data, errors

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        form_data = _build_data_without_credentials(reauth_entry.data)

        if user_input is not None:
            # Merge with existing config - empty credentials keep existing values
            merged_input = {
                **reauth_entry.data,
                **_filter_empty_credentials(user_input),
            }

            # Clear stored session if credentials changed to force fresh authentication
            await _async_clear_session_if_credentials_changed(
                self.hass, reauth_entry, merged_input
            )

            # validate login data
            _, errors = await self._async_get_nvr_data(merged_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data=_normalize_port(merged_input)
                )

        self.context["title_placeholders"] = {
            "name": reauth_entry.title,
            "ip_address": reauth_entry.data[CONF_HOST],
        }
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                "local_user_documentation_url": await async_local_user_documentation_url(
                    self.hass
                ),
            },
            data_schema=self.add_suggested_values_to_schema(REAUTH_SCHEMA, form_data),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}

        reconfigure_entry = self._get_reconfigure_entry()
        form_data = _build_data_without_credentials(reconfigure_entry.data)

        if user_input is not None:
            # Merge with existing config - empty credentials keep existing values
            merged_input = {
                **reconfigure_entry.data,
                **_filter_empty_credentials(user_input),
            }

            # Clear stored session if credentials changed to force fresh authentication
            await _async_clear_session_if_credentials_changed(
                self.hass, reconfigure_entry, merged_input
            )

            # validate login data
            nvr_data, errors = await self._async_get_nvr_data(merged_input)
            if nvr_data and not errors:
                new_unique_id = _async_unifi_mac_from_hass(nvr_data.mac)
                _LOGGER.debug(
                    "Reconfigure: Current unique_id=%s, NVR MAC=%s, formatted=%s",
                    reconfigure_entry.unique_id,
                    nvr_data.mac,
                    new_unique_id,
                )
                await self.async_set_unique_id(new_unique_id)
                self._abort_if_unique_id_mismatch(reason="wrong_nvr")

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data=_normalize_port(merged_input),
                )

        return self.async_show_form(
            step_id="reconfigure",
            description_placeholders={
                "local_user_documentation_url": await async_local_user_documentation_url(
                    self.hass
                ),
            },
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA, form_data
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            nvr_data, errors = await self._async_get_nvr_data(user_input)

            if nvr_data and not errors:
                await self.async_set_unique_id(nvr_data.mac)
                self._abort_if_unique_id_configured()

                return self._async_create_entry(nvr_data.display_name, user_input)

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "local_user_documentation_url": await async_local_user_documentation_url(
                    self.hass
                )
            },
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
        )


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                }
            ),
        )
