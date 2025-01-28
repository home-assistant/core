"""Config Flow for B-Route Meter.

This implements the UI wizard to let user input B-route ID, password,
and serial port in Home Assistant's "Integrations" page.

"""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_RETRY_COUNT,
    CONF_ROUTE_B_ID,
    CONF_ROUTE_B_PWD,
    CONF_SERIAL_PORT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_SERIAL_PORT,
    DEVICE_NAME,
    DOMAIN,
)

# We define the user step schema
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_ROUTE_B_ID, description={"suggested_value": "00000000000000000000"}
        ): str,
        vol.Required(
            CONF_ROUTE_B_PWD, description={"suggested_value": "YYYY00000000"}
        ): str,
        vol.Optional(CONF_SERIAL_PORT, default=DEFAULT_SERIAL_PORT): str,
        vol.Optional(CONF_RETRY_COUNT, default=str(DEFAULT_RETRY_COUNT)): str,
    }
)


class BRouteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """B-Route config flow.

    This class defines how the UI flow is structured (the steps),
    and how we create an entry once user completes them.
    """

    VERSION = 1

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Handle the first (and only) step of our config flow."""
        errors = {}

        if user_input is not None:
            # Validate or attempt connection here if needed
            # 必要があればここで接続テストやバリデーションを行う

            # For example, we can check if an entry with same B ID already exists
            unique_id = user_input[CONF_ROUTE_B_ID]
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # If everything is OK, create the entry
            return self.async_create_entry(
                title=f"{DEVICE_NAME} ({unique_id})",
                data=user_input,
            )

        # Show the form
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow if needed."""
        return BRouteOptionsFlow(config_entry)


class BRouteOptionsFlow(config_entries.OptionsFlow):
    """Options flow if you want to allow changing config after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        errors = {}

        if user_input is not None:
            try:
                retry_count = int(user_input[CONF_RETRY_COUNT])
                if not 1 <= retry_count <= 10:
                    errors[CONF_RETRY_COUNT] = "invalid_retry_count"
                else:
                    user_input[CONF_RETRY_COUNT] = retry_count
            except ValueError:
                errors[CONF_RETRY_COUNT] = "invalid_retry_count"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ROUTE_B_ID, default=self.config_entry.data.get(CONF_ROUTE_B_ID)
                ): str,
                vol.Required(
                    CONF_ROUTE_B_PWD,
                    default=self.config_entry.data.get(CONF_ROUTE_B_PWD),
                ): str,
                vol.Optional(
                    CONF_SERIAL_PORT,
                    default=self.config_entry.data.get(
                        CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT
                    ),
                ): str,
                vol.Optional(
                    CONF_RETRY_COUNT,
                    default=str(
                        self.config_entry.data.get(
                            CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT
                        )
                    ),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
