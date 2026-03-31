"""Config flow for the FortiOS device tracker platform."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_VDOM,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_VDOM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MINIMUM_SUPPORTED_VERSION,
)
from .firewall import FortiOSAPI

_LOGGER = logging.getLogger(__name__)


class FortiOSFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FortiOS."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = str(discovery_info.ip_address)
        port = discovery_info.port

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        self._data.update(
            {
                CONF_HOST: host,
                CONF_PORT: port,
            }
        )
        self.context.update(
            {"title_placeholders": {CONF_HOST: discovery_info.name.split(".")[0]}}
        )
        return await self.async_step_user()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        await self.async_set_unique_id(discovery_info.macaddress)
        self._abort_if_unique_id_configured()

        self._data.update({CONF_HOST: discovery_info.ip})
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        self._data.update(self._get_reconfigure_entry().data)
        return await self.async_step_user()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._data.update(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data[CONF_TOKEN] = user_input[CONF_TOKEN]
            errors = await self._async_try_connect()
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_TOKEN: user_input[CONF_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            description_placeholders={CONF_HOST: self._data.get(CONF_HOST, "")},
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            errors = await self._async_try_connect()
            if not errors:
                serial: str = self._data.pop("_serial")
                await self.async_set_unique_id(serial)
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        entry=self._get_reconfigure_entry(),
                        data=self._data,
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"FortiGate {serial}",
                    data=self._data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=self._data.get(CONF_HOST, DEFAULT_HOST),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=self._data.get(CONF_PORT, DEFAULT_PORT),
                    ): int,
                    vol.Required(
                        CONF_TOKEN,
                        default=self._data.get(CONF_TOKEN),
                    ): str,
                    vol.Required(
                        CONF_VDOM,
                        default=self._data.get(CONF_VDOM, DEFAULT_VDOM),
                    ): str,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=self._data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def _async_try_connect(self) -> dict[str, str]:
        """Try connecting to the FortiGate; return errors dict (empty on success).

        On success, stores the device serial in ``self._data["_serial"]``.
        """
        fgt = FortiOSAPI(
            self.hass,
            self._data[CONF_HOST],
            self._data[CONF_PORT],
            self._data[CONF_TOKEN],
            self._data[CONF_VDOM],
            self._data[CONF_VERIFY_SSL],
        )
        try:
            response = await fgt.get("monitor/system/status")
            version = response.get("version", "")
            if AwesomeVersion(version) < AwesomeVersion(MINIMUM_SUPPORTED_VERSION):
                _LOGGER.debug(
                    "Unsupported FortiOS version: %s (minimum: %s)",
                    version,
                    MINIMUM_SUPPORTED_VERSION,
                )
                return {"base": "unsupported_version"}
            self._data["_serial"] = response["serial"]
        except aiohttp.ClientResponseError as error:
            if error.status == 401:
                return {"base": "invalid_auth"}
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            return {"base": "unknown_error"}
        return {}
