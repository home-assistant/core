"""Config flow for AirTouch4."""

from typing import Any

from airtouch4pyapi import AirTouch, AirTouchStatus
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class AirtouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Airtouch config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}

        host = user_input[CONF_HOST]
        self._async_abort_entries_match({CONF_HOST: host})

        airtouch = AirTouch(host)
        await airtouch.UpdateInfo()
        airtouch_status = airtouch.Status
        airtouch_has_groups = bool(
            airtouch.Status == AirTouchStatus.OK and airtouch.GetGroups()
        )

        if airtouch_status != AirTouchStatus.OK:
            errors["base"] = "cannot_connect"
        elif not airtouch_has_groups:
            errors["base"] = "no_units"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        return self.async_create_entry(
            title=user_input[CONF_HOST],
            data={
                CONF_HOST: user_input[CONF_HOST],
            },
        )
