"""Config flow for the Rova platform."""

from typing import Any

from requests.exceptions import ConnectTimeout, HTTPError
from rova import rova
import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_HOUSE_NUMBER, CONF_HOUSE_NUMBER_SUFFIX, CONF_ZIP_CODE, DOMAIN


class RovaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Rova config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step when user initializes a integration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)

            zip_code = user_input[CONF_ZIP_CODE]
            number = user_input[CONF_HOUSE_NUMBER]
            suffix = user_input[CONF_HOUSE_NUMBER_SUFFIX]

            api = rova.Rova(zip_code, number, suffix)

            try:
                is_rova_area = await self.hass.async_add_executor_job(api.is_rova_area)
            except (ConnectTimeout, HTTPError):
                errors = {"base": "could_not_connect"}

            if is_rova_area:
                return self.async_create_entry(
                    title=f"{zip_code} {number} {suffix}".strip(),
                    data={
                        CONF_ZIP_CODE: zip_code,
                        CONF_HOUSE_NUMBER: number,
                        CONF_HOUSE_NUMBER_SUFFIX: suffix,
                    },
                )

            errors = {"base": "invalid_rova_area"}

        else:
            user_input = {
                CONF_ZIP_CODE: "",
                CONF_HOUSE_NUMBER: "",
                CONF_HOUSE_NUMBER_SUFFIX: "",
            }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZIP_CODE, default=user_input[CONF_ZIP_CODE]): str,
                    vol.Required(
                        CONF_HOUSE_NUMBER, default=user_input[CONF_HOUSE_NUMBER]
                    ): str,
                    vol.Optional(
                        CONF_HOUSE_NUMBER_SUFFIX,
                        default=user_input[CONF_HOUSE_NUMBER_SUFFIX],
                    ): str,
                }
            ),
            errors=errors,
        )
