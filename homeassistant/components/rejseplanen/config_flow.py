"""Config flow for Rejseplanen integration."""

from py_rejseplan.api.base import baseAPIClient as Rejseplanen
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_AUTHENTICATION,
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_NAME,
    CONF_ROUTE,
    CONF_STOP_ID,
    DEFAULT_STOP_NAME,
    DEPARTURE_TYPE_OPTIONS,
    DEPARTURE_TYPE_TO_CLASS,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTHENTICATION): str,
    }
)

CONFIG_STOP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STOP_ID): NumberSelector(
            NumberSelectorConfig(
                mode=NumberSelectorMode.BOX, min=1, max=999999999, step=1
            ),
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_STOP_NAME): str,
        vol.Optional(CONF_DIRECTION, default=[]): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            )
        ),
        vol.Optional(
            CONF_DEPARTURE_TYPE,
            default=[],
        ): cv.multi_select(DEPARTURE_TYPE_OPTIONS),
    }
)


class RejseplanenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configflow for Rejseplanen integration."""

    VERSION = 1
    MINOR_VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"stop": RejseplanenSubentryStopFlow}

    async def async_step_user(
        self,
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=CONFIG_SCHEMA,
                description_placeholders={"name": "Rejseplanen"},
            )
        await self.async_set_unique_id(user_input[CONF_AUTHENTICATION])
        self._abort_if_unique_id_configured()

        # Validate authentication key
        auth_key = user_input[CONF_AUTHENTICATION]
        api = Rejseplanen(base_url="https://www.rejseplanen.dk/api/", auth_key=auth_key)
        result = await self.hass.async_add_executor_job(api.validate_auth_key)
        if not result:
            return self.async_show_form(
                step_id="user",
                data_schema=CONFIG_SCHEMA,
                errors={"base": "invalid_auth"},
            )

        # Store the authentication key and name
        return self.async_create_entry(
            title="Rejseplanen",
            data={CONF_AUTHENTICATION: auth_key, CONF_NAME: "Rejseplanen"},
        )


class RejseplanenSubentryStopFlow(ConfigSubentryFlow):
    """Handle subentry flow for Rejseplanen stops."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, str] | None = None,
    ) -> SubentryFlowResult:
        """Handle the stop subentry step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_STOP_SCHEMA)

        stop_id = int(user_input[CONF_STOP_ID])
        name = user_input[CONF_NAME]

        selected_keys: str | list = user_input.get(CONF_DEPARTURE_TYPE, [])
        departure_types = [
            DEPARTURE_TYPE_TO_CLASS[key]
            for key in selected_keys
            if key in DEPARTURE_TYPE_TO_CLASS
        ]

        return self.async_create_entry(
            title=name,
            data={
                CONF_STOP_ID: stop_id,
                CONF_NAME: name,
                CONF_DEPARTURE_TYPE: departure_types,
                CONF_DIRECTION: user_input.get(CONF_DIRECTION, []),
                CONF_ROUTE: user_input.get(CONF_ROUTE, []),
            },
        )
