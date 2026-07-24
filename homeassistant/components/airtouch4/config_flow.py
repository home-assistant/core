"""Config flow for AirTouch4."""

from typing import Any, override

from airtouch4pyapi import AirTouch, AirTouchStatus, AirTouchVersion
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN, PORT

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class AirtouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Airtouch config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}

        host = user_input[CONF_HOST]
        self._async_abort_entries_match({CONF_HOST: host})

        # Pass the version and port explicitly so the library does not probe for
        # the protocol version, which opens a blocking socket in the event loop.
        airtouch = AirTouch(host, AirTouchVersion.AIRTOUCH4, PORT)
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
