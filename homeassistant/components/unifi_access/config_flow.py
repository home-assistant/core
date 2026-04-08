"""Config flow for UniFi Access integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from unifi_access_api import ApiAuthError, ApiConnectionError, UnifiAccessApiClient
from unifi_discovery import async_console_is_alive
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.util.network import is_ip_address
from homeassistant.util.ssl import create_no_verify_ssl_context

from .const import DOMAIN
from .discovery import async_start_discovery

_LOGGER = logging.getLogger(__name__)

ENTRY_FAILURE_STATES = (
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
)


@callback
def _last_update_was_successful(entry: ConfigEntry) -> bool:
    """Check if the last coordinator update was successful.

    Returns True when runtime_data is not set (e.g. setup failed before
    the coordinator was stored). In that case the entry state will already
    be in ENTRY_FAILURE_STATES, so the caller still detects the problem.
    """
    runtime_data = getattr(entry, "runtime_data", None)
    return runtime_data is None or runtime_data.last_update_success


async def _async_console_is_offline(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Check if a console is offline."""
    return bool(
        entry.state in ENTRY_FAILURE_STATES or not _last_update_was_successful(entry)
    ) and not await async_console_is_alive(
        async_get_clientsession(hass, verify_ssl=False), entry.data[CONF_HOST]
    )


def _format_mac(mac: str) -> str:
    """Format a MAC address to uppercase without separators."""
    return mac.replace(":", "").replace("-", "").upper()


class UnifiAccessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UniFi Access."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Init the config flow."""
        super().__init__()
        self._discovered_device: dict[str, Any] = {}

    async def _validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate user input and return errors dict."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(
            self.hass, verify_ssl=user_input[CONF_VERIFY_SSL]
        )
        ssl_context = (
            None if user_input[CONF_VERIFY_SSL] else create_no_verify_ssl_context()
        )
        client = UnifiAccessApiClient(
            host=user_input[CONF_HOST],
            api_token=user_input[CONF_API_TOKEN],
            session=session,
            verify_ssl=user_input[CONF_VERIFY_SSL],
            ssl_context=ssl_context,
        )
        try:
            await client.authenticate()
        except ApiAuthError:
            try:
                is_protect = await client.is_protect_api_key()
            except Exception:  # noqa: BLE001
                is_protect = False
            errors["base"] = "protect_api_key" if is_protect else "invalid_auth"
        except ApiConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return errors

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
        async_start_discovery(self.hass)
        return self.async_abort(reason="discovery_started")

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        self._discovered_device = discovery_info
        mac = _format_mac(discovery_info["hw_addr"])
        await self.async_set_unique_id(mac)
        source_ip = discovery_info["source_ip"]

        # Only update the host if the stored value is an IP address,
        # not a user-provided hostname like "unifi.local",
        # and only if the existing host is unreachable.
        updates: dict[str, Any] | None = None
        for entry in self._async_current_entries():
            if (
                entry.unique_id == mac
                and is_ip_address(entry.data.get(CONF_HOST, ""))
                and entry.data[CONF_HOST] != source_ip
                and await _async_console_is_offline(self.hass, entry)
            ):
                updates = {CONF_HOST: source_ip}
                break
        self._abort_if_unique_id_configured(updates=updates)

        # If a manually created entry exists for this host without a unique_id,
        # adopt it by setting the unique_id so future discoveries can update its IP.
        for entry in self._async_current_entries():
            if entry.unique_id is None and entry.data.get(CONF_HOST) == source_ip:
                self.hass.config_entries.async_update_entry(entry, unique_id=mac)
                return self.async_abort(reason="already_configured")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}
        discovery_info = self._discovered_device
        name = (
            discovery_info.get("hostname")
            or discovery_info.get("platform")
            or "UniFi Console"
        )

        if user_input is not None:
            data = {**user_input, CONF_HOST: discovery_info["source_ip"]}
            errors = await self._validate_input(data)
            if not errors:
                return self.async_create_entry(
                    title=name,
                    data=data,
                )

        placeholders = {
            "name": name,
            "ip_address": discovery_info["source_ip"],
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=placeholders,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): str,
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            errors = await self._validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title="UniFi Access",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_API_TOKEN): str,
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST]},
            )
            errors = await self._validate_input(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

        suggested_values = user_input or dict(reconfigure_entry.data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_API_TOKEN): str,
                        vol.Required(CONF_VERIFY_SSL): bool,
                    }
                ),
                suggested_values,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirm."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            errors = await self._validate_input(
                {
                    **reauth_entry.data,
                    CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                }
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            description_placeholders={CONF_HOST: reauth_entry.data[CONF_HOST]},
            errors=errors,
        )
