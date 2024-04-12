"""Config flow for RTSPtoWebRTC."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import rtsp_to_webrtc
import voluptuous as vol

from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import CONF_STUN_SERVER, DATA_SERVER_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(DATA_SERVER_URL): str})


class RTSPToWebRTCConfigFlow(ConfigFlow, domain=DOMAIN):
    """RTSPtoWebRTC config flow."""

    _hassio_discovery: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the RTSPtoWebRTC server url."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        url = user_input[DATA_SERVER_URL]
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={DATA_SERVER_URL: "invalid_url"},
            )

        if error_code := await self._test_connection(url):
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base": error_code},
            )

        await self.async_set_unique_id(DOMAIN)
        return self.async_create_entry(
            title=url,
            data={DATA_SERVER_URL: url},
        )

    async def _test_connection(self, url: str) -> str | None:
        """Test the connection and return any relevant errors."""
        client = rtsp_to_webrtc.client.Client(async_get_clientsession(self.hass), url)
        try:
            await client.heartbeat()
        except rtsp_to_webrtc.exceptions.ResponseError as err:
            _LOGGER.error("RTSPtoWebRTC server failure: %s", str(err))
            return "server_failure"
        except rtsp_to_webrtc.exceptions.ClientError as err:
            _LOGGER.error("RTSPtoWebRTC communication failure: %s", str(err))
            return "server_unreachable"
        return None

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for the RTSPtoWebRTC server add-on discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self._hassio_discovery = discovery_info.config
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Add-on discovery."""
        errors = None
        if user_input is not None:
            # Validate server connection once user has confirmed
            host = self._hassio_discovery[CONF_HOST]
            port = self._hassio_discovery[CONF_PORT]
            url = f"http://{host}:{port}"
            if error_code := await self._test_connection(url):
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
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create an options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """RTSPtoWeb Options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

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
