"""Config flow for RTSPtoWebRTC."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import rtsp_to_webrtc
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import CONF_STUN_SERVER, DATA_SERVER_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({})


async def _test_connection(hass: HomeAssistant, url: str) -> str | None:
    """Test the connection and return any relevant errors."""
    result = urlparse(url)
    if not all([result.scheme, result.netloc]):
        return "invalid_url"
    client = rtsp_to_webrtc.client.Client(async_get_clientsession(hass), url)
    try:
        await client.heartbeat()
    except rtsp_to_webrtc.exceptions.ResponseError as err:
        _LOGGER.error("RTSPtoWebRTC server failure: %s", str(err))
        return "server_failure"
    except rtsp_to_webrtc.exceptions.ClientError as err:
        _LOGGER.error("RTSPtoWebRTC communication failure: %s", str(err))
        return "server_unreachable"
    return None


class RTSPToWebRTCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """RTSPtoWebRTC config flow."""

    _hassio_discovery: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the RTSPtoWebRTC server."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        self._set_confirm_only()
        await self.async_set_unique_id(DOMAIN)
        return self.async_create_entry(
            title=DOMAIN,
            data={},
            options={DATA_SERVER_URL: None},
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user({})

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Prepare configuration for the RTSPtoWebRTC server add-on discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self._hassio_discovery = discovery_info.config
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Add-on discovery."""
        errors = None
        if user_input is not None:
            # Validate server connection once user has confirmed
            host = self._hassio_discovery[CONF_HOST]
            port = self._hassio_discovery[CONF_PORT]
            url = f"http://{host}:{port}"
            if error_code := await _test_connection(self.hass, url):
                return self.async_abort(reason=error_code)

        if user_input is None or errors:
            # Show initial confirmation or errors from server validation
            return self.async_show_form(
                step_id="hassio_confirm",
                description_placeholders={"addon": self._hassio_discovery["addon"]},
                errors=errors,
            )

        return self.async_create_entry(
            title=self._hassio_discovery["addon"],
            data={DATA_SERVER_URL: url},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create an options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """RTSPtoWeb Options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (url := user_input.get(DATA_SERVER_URL)) or not (
                error_code := await _test_connection(self.hass, url)
            ):
                return self.async_create_entry(title="", data=user_input)
            errors = {DATA_SERVER_URL: error_code}

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        DATA_SERVER_URL,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                DATA_SERVER_URL
                            ),
                        },
                    ): str,
                    vol.Optional(
                        CONF_STUN_SERVER,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_STUN_SERVER
                            ),
                        },
                    ): str,
                }
            ),
        )
