"""Config flow for Avri component."""
import pycountry
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ID

from .const import (
    CONF_COUNTRY_CODE,
    CONF_HOUSE_NUMBER,
    CONF_HOUSE_NUMBER_EXTENSION,
    CONF_ZIP_CODE,
    DEFAULT_COUNTRY_CODE,
)
from .const import DOMAIN  # pylint:disable=unused-import

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZIP_CODE): str,
        vol.Required(CONF_HOUSE_NUMBER): int,
        vol.Optional(CONF_HOUSE_NUMBER_EXTENSION): str,
        vol.Optional(CONF_COUNTRY_CODE, default=DEFAULT_COUNTRY_CODE): str,
    }
)


class AvriConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Avri config flow."""

    VERSION = 1

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return await self._show_setup_form()

        zip_code = user_input[CONF_ZIP_CODE].replace(" ", "").upper()

        errors = {}
        if user_input[CONF_HOUSE_NUMBER] <= 0:
            errors[CONF_HOUSE_NUMBER] = "invalid_house_number"
            return await self._show_setup_form(errors)
        if not pycountry.countries.get(alpha_2=user_input[CONF_COUNTRY_CODE]):
            errors[CONF_COUNTRY_CODE] = "invalid_country_code"
            return await self._show_setup_form(errors)

        unique_id = (
            f"{zip_code}"
            f" "
            f"{user_input[CONF_HOUSE_NUMBER]}"
            f'{user_input.get(CONF_HOUSE_NUMBER_EXTENSION, "")}'
        )

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_ID: unique_id,
                CONF_ZIP_CODE: zip_code,
                CONF_HOUSE_NUMBER: user_input[CONF_HOUSE_NUMBER],
                CONF_HOUSE_NUMBER_EXTENSION: user_input.get(
                    CONF_HOUSE_NUMBER_EXTENSION, ""
                ),
                CONF_COUNTRY_CODE: user_input[CONF_COUNTRY_CODE],
            },
        )
