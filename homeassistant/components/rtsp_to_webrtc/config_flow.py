"""Config flow for RTSPtoWebRTC."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import rtsp_to_webrtc
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DATA_SERVER_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(DATA_SERVER_URL): str})


class RTSPToWebRTCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """RTSPtoWebRTC config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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

        errors = {}
        client = rtsp_to_webrtc.client.Client(async_get_clientsession(self.hass), url)
        try:
            await client.heartbeat()
        except rtsp_to_webrtc.exceptions.ResponseError as err:
            _LOGGER.error("RTSPtoWebRTC server failure: %s", str(err))
            errors["base"] = "server_failure"
        except rtsp_to_webrtc.exceptions.ClientError as err:
            _LOGGER.error("RTSPtoWebRTC communication failure: %s", str(err))
            errors["base"] = "server_unreachable"
        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors=errors,
            )

        await self.async_set_unique_id(DOMAIN)
        return self.async_create_entry(
            title=url,
            data={DATA_SERVER_URL: url},
        )
