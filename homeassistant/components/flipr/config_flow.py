"""Config flow for Flipr integration."""

from __future__ import annotations

import logging
from typing import Any

from flipr_api import FliprAPIRestClient
from requests.exceptions import HTTPError, Timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class FliprConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flipr."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            client = FliprAPIRestClient(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )

            try:
                ids = await self.hass.async_add_executor_job(client.search_all_ids)
            except HTTPError:
                errors["base"] = "invalid_auth"
            except (Timeout, ConnectionError):
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected exception")

            else:
                _LOGGER.debug("Found flipr or hub ids : %s", ids)

                if len(ids["flipr"]) > 0 or len(ids["hub"]) > 0:
                    # If there is a flipr or hub, we can create a config entry.

                    await self.async_set_unique_id(user_input[CONF_EMAIL])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Flipr {user_input[CONF_EMAIL]}",
                        data=user_input,
                    )

                # if no flipr or hub found. Tell the user with an error message.
                errors["base"] = "no_flipr_id_found"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
