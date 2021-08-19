"""Adds config flow for Barry integration."""
# pylint: disable=attribute-defined-outside-init
import asyncio

from pybarry import Barry, InvalidToken
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import DOMAIN, PRICE_CODE


class BarryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Barry integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        data_schema = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN].replace(" ", "")

            barry_connection = Barry(
                access_token=access_token,
            )

            errors = {}
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, barry_connection.get_all_metering_points, True
                )
            except InvalidToken:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"
            except Exception:  # pylint: disable=broad-except
                errors[CONF_ACCESS_TOKEN] = "unknown"

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors=errors,
                )
            self.init_info = barry_connection
            return await self.async_step_metering_point()

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    async def async_step_metering_point(self, user_input=None):
        """Handle the metering point selection step."""
        mpids = self.init_info.get_all_metering_points()
        mpids_display = [mpid[0] for mpid in mpids]
        data_schema = vol.Schema(
            {vol.Required("metering_point"): vol.In(mpids_display)}
        )
        if user_input:
            selected_meter = user_input["metering_point"]
            price_code = ""
            for mpid, code in mpids:
                if mpid == selected_meter:
                    price_code = code
            self.hass.data[PRICE_CODE] = price_code

            unique_id = str(selected_meter) + "_spot_price"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Barry",
                data={
                    CONF_ACCESS_TOKEN: self.init_info.access_token,
                    PRICE_CODE: price_code,
                },
            )

        return self.async_show_form(
            step_id="metering_point",
            data_schema=data_schema,
        )
