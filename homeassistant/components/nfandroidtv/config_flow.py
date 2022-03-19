"""Config flow for NFAndroidTV integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientConnectorError
from notifications_android_tv.notifications import ConnectError, Notifications
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import ANDROID_TV_NAME, DEFAULT_NAME, DOMAIN, FIRE_TV_NAME, PLACEHOLDERS

_LOGGER = logging.getLogger(__name__)


class NFAndroidTVFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NFAndroidTV."""

    def __init__(self) -> None:
        """Initialize an NFAndroidTV flow."""
        self.ip_address = ""

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> FlowResult:
        """Handle dhcp discovery."""
        self.ip_address = discovery_info.ip
        mac = format_mac(discovery_info.macaddress)
        _LOGGER.warning(discovery_info)

        if existing_entry := await self.async_set_unique_id(discovery_info.ip):
            self.hass.config_entries.async_update_entry(existing_entry, unique_id=mac)
            return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        if "amazon-" in discovery_info.hostname:
            session = async_get_clientsession(self.hass)
            # A valid fire stick device should have this port open
            try:
                await session.get(f"http://{discovery_info.ip}:8009")
            except ClientConnectorError:
                return self.async_abort(reason="not_valid_device")
            return await self.async_step_confirm_discovery_fire_tv()
        return await self.async_step_confirm_discovery_android_tv()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            self._async_abort_entries_match({CONF_HOST: host})
            await self.async_set_unique_id(host)
            error = await self._async_try_connect(host)
            if error is None:
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_NAME: name},
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                }
            ),
            description_placeholders=PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_confirm_discovery_fire_tv(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the Fire TV device."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: self.ip_address})
            error = await self._async_try_connect(self.ip_address)
            if error is None:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_HOST: self.ip_address, CONF_NAME: user_input[CONF_NAME]},
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="confirm_discovery_fire_tv",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME,
                        default=user_input.get(
                            CONF_NAME, f"{FIRE_TV_NAME} {self.ip_address}"
                        ),
                    ): str,
                }
            ),
            description_placeholders=PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_confirm_discovery_android_tv(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the Android TV device."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: self.ip_address})
            error = await self._async_try_connect(self.ip_address)
            if error is None:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_HOST: self.ip_address, CONF_NAME: user_input[CONF_NAME]},
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="confirm_discovery_android_tv",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME,
                        default=user_input.get(
                            CONF_NAME, f"{ANDROID_TV_NAME} {self.ip_address}"
                        ),
                    ): str,
                }
            ),
            description_placeholders=PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == import_config[CONF_HOST]:
                _LOGGER.warning(
                    "Already configured. This yaml configuration has already been imported. Please remove it"
                )
                return self.async_abort(reason="already_configured")
        if CONF_NAME not in import_config:
            import_config[CONF_NAME] = f"{DEFAULT_NAME} {import_config[CONF_HOST]}"

        return await self.async_step_user(import_config)

    async def _async_try_connect(self, host: str) -> str | None:
        """Try connecting to Android TV / Fire TV."""
        try:
            await self.hass.async_add_executor_job(Notifications, host)
        except ConnectError:
            if self.ip_address:
                return "check_device"
            return "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None
