"""Adds config flow for Barry integration."""
from pybarry import Barry, InvalidToken
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import DOMAIN  # pylint:disable=unused-import


class BarryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Barry integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        DATA_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN].replace(" ", "")

            barry_connection = Barry(
                access_token=access_token,
            )

            errors = {}
            try:
                barry_connection.get_all_metering_points(check_token=True)
            except InvalidToken:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    errors=errors,
                )
            self.init_info = barry_connection
            return await self.async_step_metering_point()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors={},
        )

    async def async_step_metering_point(self, user_input=None):
        """Handle the metering point selection step."""
        mpids = self.init_info.get_all_metering_points()
        mpids_display = [mpid[0] for mpid in mpids]
        DATA_SCHEMA = vol.Schema(
            {vol.Required("metering_point"): vol.In(mpids_display)}
        )
        errors = {}
        if user_input:
            try:
                selected_meter = user_input["metering_point"]
                price_code = ""
                for mpid, code in mpids:
                    if mpid == selected_meter:
                        price_code = code
            except InvalidToken:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"
            self.hass.data["priceCode"] = price_code

            unique_id = "Qswrasdr"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Barry",
                data={
                    CONF_ACCESS_TOKEN: self.init_info.access_token,
                    "priceCode": price_code,
                },
            )

        return self.async_show_form(
            step_id="metering_point",
            data_schema=DATA_SCHEMA,
            errors={},
        )
