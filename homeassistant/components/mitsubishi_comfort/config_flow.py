"""Config flow for Mitsubishi Comfort integration."""

from __future__ import annotations

import logging
from typing import Any

from mitsubishi_comfort import MitsubishiCloudAccount
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class MitsubishiComfortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Mitsubishi Comfort."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user setup step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            account = MitsubishiCloudAccount(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )

            try:
                if not await account.login():
                    errors["base"] = "invalid_auth"
                else:
                    devices = await account.discover_devices()
                    if not devices:
                        errors["base"] = "cannot_connect"
                    else:
                        return self.async_create_entry(
                            title=f"Mitsubishi Comfort ({user_input[CONF_USERNAME]})",
                            data={
                                CONF_USERNAME: user_input[CONF_USERNAME],
                                CONF_PASSWORD: user_input[CONF_PASSWORD],
                            },
                        )
            except OSError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            finally:
                await account.close()

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )
