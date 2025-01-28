"""Config flow for SPC integration."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError
from pyspcwebgw import SpcWebGateway

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from . import CONF_API_URL, CONF_WS_URL, DATA_SCHEMA, DOMAIN


async def validate_connection(
    hass: HomeAssistant, api_url: str, ws_url: str
) -> tuple[str | None, dict[str, Any] | None]:
    """Test if we can connect to the SPC controller.

    Returns a tuple of (error, device_info).
    """
    session = aiohttp_client.async_get_clientsession(hass)

    try:
        spc = SpcWebGateway(
            loop=hass.loop,
            session=session,
            api_url=api_url,
            ws_url=ws_url,
            async_callback=None,  # No callback needed for validation
        )
        if not await spc.async_load_parameters():
            return "cannot_connect", None
        return None, spc.info  # noqa: TRY300
    except (ClientError, TimeoutError, Exception):  # pylint: disable=broad-except
        return "cannot_connect", None


class SpcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SPC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_API_URL: user_input[CONF_API_URL],
                    CONF_WS_URL: user_input[CONF_WS_URL],
                }
            )

            error, device_info = await validate_connection(
                self.hass,
                user_input[CONF_API_URL],
                user_input[CONF_WS_URL],
            )
            if error is None and device_info is not None:
                return self.async_create_entry(
                    title=f"{device_info['type']} - {device_info['sn']}",
                    data=user_input,
                )

            if error:
                errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        self._async_abort_entries_match(
            {
                CONF_API_URL: import_config[CONF_API_URL],
                CONF_WS_URL: import_config[CONF_WS_URL],
            }
        )

        error, device_info = await validate_connection(
            self.hass,
            import_config[CONF_API_URL],
            import_config[CONF_WS_URL],
        )

        if error is None and device_info is not None:
            return self.async_create_entry(
                title=f"{device_info['type']} - {device_info['sn']}",
                data=import_config,
            )

        return self.async_abort(reason=error or "cannot_connect")
