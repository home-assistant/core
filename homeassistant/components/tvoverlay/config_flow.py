"""Config flow for TvOverlay integration."""
from __future__ import annotations

import logging
from typing import Any

from tvoverlay import Notifications
from tvoverlay.exceptions import ConnectError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TvOverlayFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TvOverlay."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_NAME: user_input[CONF_NAME]}
            )
            error, info = await self._async_try_connect(user_input[CONF_HOST])
            if error is not None:
                errors["base"] = error
            elif info is not None:
                device_name = (
                    info.get("result", {})
                    .get("settings", {})
                    .get("deviceName", DEFAULT_NAME)
                )
                unique_id = (
                    device_name.replace(" ", "_")
                    + "_"
                    + str.replace(user_input[CONF_HOST], ".", "_")
                )
                await self.async_set_unique_id(unique_id)
                if user_input[CONF_NAME] == DEFAULT_NAME:
                    user_input[CONF_NAME] = device_name
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )

    async def _async_try_connect(
        self, host: str
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Try connecting to TvOverlay."""
        notifier = Notifications(host)
        try:
            info = await notifier.async_connect()
            _LOGGER.debug("TvOverlay device info for host %s: %s", host, info)
        except ConnectError:
            _LOGGER.error("Error connecting to device at %s", host)
            return "cannot_connect", None
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception: %s", ex)
            return "unknown", None
        return None, info
