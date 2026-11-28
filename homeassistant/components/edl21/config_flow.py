"""Config flow for EDL21 integration."""

from typing import Any, override

import probatio

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.field_visibility import FieldCondition
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
)

from .const import (
    CONF_LIMIT_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_UPDATE_INTERVAL,
    DEFAULT_LIMITED_UPDATE_INTERVAL,
    DEFAULT_TITLE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
)

LIMIT_INTERVAL_SELECTOR = BooleanSelector()

UPDATE_INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=1,
        max=MAX_UPDATE_INTERVAL,
        step=1,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="s",
    )
)

LIMIT_INTERVAL_CONDITION: FieldCondition = {
    "field": CONF_LIMIT_INTERVAL,
    "value": True,
}

LIMIT_INTERVAL_SCHEMA_FIELDS = {
    probatio.Optional(CONF_LIMIT_INTERVAL, default=False): LIMIT_INTERVAL_SELECTOR,
    # Approved exemption: the interval throttles forwarding telegrams to the
    # recorder (event-driven meter, not polling); the value is device-driven.
    # pylint: disable-next=home-assistant-config-flow-polling-field
    data_entry_flow.Optional(
        CONF_UPDATE_INTERVAL,
        default=DEFAULT_LIMITED_UPDATE_INTERVAL,
        visible=LIMIT_INTERVAL_CONDITION,
    ): UPDATE_INTERVAL_SELECTOR,
}

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_SERIAL_PORT): SerialPortSelector(),
        **LIMIT_INTERVAL_SCHEMA_FIELDS,
    }
)

OPTIONS_SCHEMA = probatio.Schema({**LIMIT_INTERVAL_SCHEMA_FIELDS})


def _update_interval_from_user_input(
    user_input: dict[str, Any], errors: dict[str, str]
) -> int | None:
    """Convert form input to a stored update interval; populate errors on failure.

    The checkbox is the single switch for throttling: unchecked means every
    telegram update is forwarded (stored interval 0), checked means at most one
    update per the given number of seconds. The flow manager fills schema
    defaults and validates the selector range before this runs; the checks here
    are a backend-side guard for API clients that bypass the form.
    """
    if not user_input.get(CONF_LIMIT_INTERVAL, False):
        return 0
    try:
        interval = int(
            user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_LIMITED_UPDATE_INTERVAL)
        )
    except TypeError, ValueError:
        interval = -1
    if not 1 <= interval <= MAX_UPDATE_INTERVAL:
        errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
        return None
    return interval


class EDL21OptionsFlow(OptionsFlow):
    """Handle EDL21 options."""

    def _options_schema(
        self, user_input: dict[str, Any] | None = None
    ) -> probatio.Schema:
        """Build the options form schema with prefilled suggested values."""
        if user_input is not None:
            limit = user_input.get(CONF_LIMIT_INTERVAL, False)
            interval = user_input.get(
                CONF_UPDATE_INTERVAL, DEFAULT_LIMITED_UPDATE_INTERVAL
            )
        else:
            current_interval = int(
                self.config_entry.options.get(
                    CONF_UPDATE_INTERVAL,
                    self.config_entry.data.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                )
            )
            limit = current_interval > 0
            interval = (
                current_interval
                if current_interval > 0
                else DEFAULT_LIMITED_UPDATE_INTERVAL
            )
        return self.add_suggested_values_to_schema(
            OPTIONS_SCHEMA,
            {CONF_LIMIT_INTERVAL: limit, CONF_UPDATE_INTERVAL: interval},
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage EDL21 options."""
        if user_input is not None:
            errors: dict[str, str] = {}
            interval = _update_interval_from_user_input(user_input, errors)
            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._options_schema(user_input),
                    errors=errors,
                )
            return self.async_create_entry(
                title="", data={CONF_UPDATE_INTERVAL: interval}
            )

        return self.async_show_form(step_id="init", data_schema=self._options_schema())


class EDL21ConfigFlow(ConfigFlow, domain=DOMAIN):
    """EDL21 config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the user setup step."""
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT]}
            )

            errors: dict[str, str] = {}
            interval = _update_interval_from_user_input(user_input, errors)
            if errors:
                data_schema = self.add_suggested_values_to_schema(
                    DATA_SCHEMA, user_input
                )
                return self.async_show_form(
                    step_id="user", data_schema=data_schema, errors=errors
                )

            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data={
                    CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT],
                    CONF_UPDATE_INTERVAL: interval,
                },
            )

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input)
        return self.async_show_form(step_id="user", data_schema=data_schema)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> EDL21OptionsFlow:
        """Get the options flow for this handler."""
        return EDL21OptionsFlow()
