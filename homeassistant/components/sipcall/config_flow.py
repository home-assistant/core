"""Config flow for SIP Call integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from .const import CONF_SIP_DOMAIN, CONF_SIP_SERVER, DOMAIN
from .notify import SIPCallNotificationService

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SIP_SERVER): str,
        vol.Required(CONF_SIP_DOMAIN): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SIP Call."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_try_dummy_call(user_input)
            if error is not None:
                errors["base"] = error
            else:
                entry_title = (
                    f"{user_input[CONF_USERNAME]}_{user_input[CONF_SIP_DOMAIN]}"
                )
                return self.async_create_entry(
                    title=entry_title, data=user_input | {CONF_NAME: entry_title}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def _async_try_dummy_call(self, user_input: dict[str, Any]) -> str | None:
        """Try to make a dummy call to see if the credentials are ok.

        Note that this call will always fail, but it should fail with a 404, because
        the called participant cannot be found.
        If it fails with an authentication error, we know the credentials are wrong.
        """

        try:
            await SIPCallNotificationService.make_call(
                user_input, "NONEXISTENT_DUMMY_CALLEE", 5
            )
        except OSError as e:
            if "404" in str(e) or "486" in str(e):
                # This is the expected result (did not find callee).
                # Some servers also return BUSY (486) in this case.
                return None

            if "401" in str(e) or "403" in str(e) or "407" in str(e):
                # Authentication failed
                return "invalid_auth"

            # Some other problem
            _LOGGER.warning("Entry verification for sipcall failed: %s", str(e))

            # To not block the user in this case, we let them add the entry nevertheless
            return None

        # This dummy call should not finish without error
        return "unknown"
