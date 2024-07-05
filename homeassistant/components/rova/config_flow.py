"""Config flow for the Rova platform."""

from typing import Any

from requests.exceptions import ConnectTimeout, HTTPError
from rova.rova import Rova
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_HOUSE_NUMBER, CONF_HOUSE_NUMBER_SUFFIX, CONF_ZIP_CODE, DOMAIN


class RovaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Rova config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # generate unique name for rova integration
            zip_code = user_input[CONF_ZIP_CODE]
            number = user_input[CONF_HOUSE_NUMBER]
            suffix = user_input[CONF_HOUSE_NUMBER_SUFFIX]

            await self.async_set_unique_id(f"{zip_code}{number}{suffix}".strip())
            self._abort_if_unique_id_configured()

            api = Rova(zip_code, number, suffix)

            try:
                if not await self.hass.async_add_executor_job(api.is_rova_area):
                    errors = {"base": "invalid_rova_area"}
            except (ConnectTimeout, HTTPError):
                errors = {"base": "cannot_connect"}

            if not errors:
                return self.async_create_entry(
                    title=f"{zip_code} {number} {suffix}".strip(),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_ZIP_CODE): str,
                        vol.Required(CONF_HOUSE_NUMBER): str,
                        vol.Optional(CONF_HOUSE_NUMBER_SUFFIX, default=""): str,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import the yaml config."""
        zip_code = user_input[CONF_ZIP_CODE]
        number = user_input[CONF_HOUSE_NUMBER]
        suffix = user_input[CONF_HOUSE_NUMBER_SUFFIX]

        await self.async_set_unique_id(f"{zip_code}{number}{suffix}".strip())
        self._abort_if_unique_id_configured()

        api = Rova(zip_code, number, suffix)

        try:
            result = await self.hass.async_add_executor_job(api.is_rova_area)

            if result:
                return self.async_create_entry(
                    title=f"{zip_code} {number} {suffix}".strip(),
                    data={
                        CONF_ZIP_CODE: zip_code,
                        CONF_HOUSE_NUMBER: number,
                        CONF_HOUSE_NUMBER_SUFFIX: suffix,
                    },
                )
            return self.async_abort(reason="invalid_rova_area")

        except (ConnectTimeout, HTTPError):
            return self.async_abort(reason="cannot_connect")
