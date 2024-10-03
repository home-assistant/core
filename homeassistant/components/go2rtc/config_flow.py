"""Config flow for WebRTC."""

from __future__ import annotations

import shutil
from typing import Any
from urllib.parse import urlparse

from go2rtc_client import Go2RtcClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.package import is_docker_env

from .const import CONF_BINARY, DOMAIN

_VALID_URL_SCHEMA = {"http", "https"}


async def _validate_url(
    hass: HomeAssistant,
    value: str,
) -> str | None:
    """Validate the URL and return error or None if it's valid."""
    if urlparse(value).scheme not in _VALID_URL_SCHEMA:
        return "invalid_url_schema"
    try:
        vol.Schema(vol.Url())(value)
    except vol.Invalid:
        return "invalid_url"

    try:
        client = Go2RtcClient(async_get_clientsession(hass), value)
        await client.streams.list()
    except Exception:  # noqa: BLE001
        return "cannot_connect"
    return None


class Go2RTCConfigFlow(ConfigFlow, domain=DOMAIN):
    """go2rtc config flow."""

    def _get_binary(self) -> str | None:
        """Return the binary path if found."""
        return shutil.which(DOMAIN)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Init step."""
        if is_docker_env() and (binary := self._get_binary()):
            return self.async_create_entry(
                title=DOMAIN,
                data={CONF_BINARY: binary, CONF_HOST: "http://localhost:1984/"},
            )

        return await self.async_step_host()

    async def async_step_host(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to use selfhosted go2rtc server."""
        errors = {}
        if user_input is not None:
            if error := await _validate_url(self.hass, user_input[CONF_HOST]):
                errors[CONF_HOST] = error
            else:
                return self.async_create_entry(title=DOMAIN, data=user_input)

        return self.async_show_form(
            step_id="host",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.URL
                            )
                        ),
                    }
                ),
                suggested_values=user_input,
            ),
            errors=errors,
            last_step=True,
        )
