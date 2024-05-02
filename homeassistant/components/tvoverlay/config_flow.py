"""Config flow for TvOverlay integration."""

from __future__ import annotations

import logging
from typing import Any

from tvoverlay import Notifications
from tvoverlay.exceptions import ConnectError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TvOverlayFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TvOverlay."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            result = await self._async_try_connect(user_input[CONF_HOST])
            error = result["error"]
            info = result["info"]
            if error is not None:
                errors["base"] = error
            elif info is not None:
                result = info.get("result", {})
                settings = result.get("settings")
                status = result.get("status")
                device_id = status and status.get("id")
                device_name = settings and settings.get("deviceName")
                if device_id is None or device_name is None:
                    errors["base"] = "unknown"
                else:
                    unique_id = str(device_id).replace("-", "")
                    self._async_abort_entries_match(
                        {CONF_HOST: user_input[CONF_HOST], CONF_NAME: device_name}
                    )
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    user_input[CONF_NAME] = device_name
                    return self.async_create_entry(
                        title=device_name,
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def _async_try_connect(self, host: str) -> dict[str, Any]:
        """Try connecting to TvOverlay."""
        notifier = Notifications(host)
        try:
            info = await notifier.async_connect()
        except ConnectError:
            _LOGGER.error("Error connecting to device at %s", host)
            return {"error": "cannot_connect", "info": None}
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return {"error": "unknown", "info": None}
        else:
            _LOGGER.debug("TvOverlay device info for host %s: %s", host, info)
            return {"error": None, "info": info}
