"""Config flow for the Rova platform."""

from typing import Any

from requests.exceptions import ConnectTimeout, HTTPError
from rova import rova
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_HOUSE_NUMBER,
    CONF_HOUSE_NUMBER_SUFFIX,
    CONF_ZIP_CODE,
    DEFAULT_NAME,
    DOMAIN,
)


class RovaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Rova config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}

    def _check_area(self, zip_code: str, number: str, suffix: str) -> bool:
        """Check if rova collects garbage at this location."""
        api = rova.Rova(zip_code, number, suffix)

        try:
            response = api.is_rova_area()
            if not response:
                self._errors = {"base": "invalid_rova_area"}
                return False
        except (ConnectTimeout, HTTPError):
            self._errors = {"base": "could_not_connect"}
            return False
        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step when user initializes a integration."""
        self._errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            zip_code = user_input[CONF_ZIP_CODE]
            number = user_input[CONF_HOUSE_NUMBER]
            suffix = user_input[CONF_HOUSE_NUMBER_SUFFIX]

            is_rova_area = await self.hass.async_add_executor_job(
                self._check_area, zip_code, number, suffix
            )

            if is_rova_area:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_ZIP_CODE: zip_code,
                        CONF_HOUSE_NUMBER: number,
                        CONF_HOUSE_NUMBER_SUFFIX: suffix,
                    },
                )

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
            errors=self._errors,
        )
