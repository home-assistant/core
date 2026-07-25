"""Config flow for Rejseplanen integration."""

from typing import Any, override

from py_rejseplan.api.departures import DeparturesAPIClient as Rejseplanen
from py_rejseplan.dataclasses.transport_mappings import DEPARTURE_TYPE_TO_CLASS
from py_rejseplan.exceptions import (
    APIError as RejseplanenAPIError,
    ConnectionError as RejseplanenConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_STOP_ID,
    DEFAULT_STOP_NAME,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY, default=""): str,
    }
)

CONFIG_STOP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STOP_ID): NumberSelector(
            NumberSelectorConfig(
                mode=NumberSelectorMode.BOX, min=1, max=999999999, step=1
            ),
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_STOP_NAME): str,  # pylint: disable=home-assistant-config-flow-name-field
        vol.Optional(CONF_DIRECTION, default=[]): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            )
        ),
        vol.Optional(
            CONF_DEPARTURE_TYPE,
            default=[],
        ): SelectSelector(
            SelectSelectorConfig(
                options=list(DEPARTURE_TYPE_TO_CLASS),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="departure_type",
                multiple=True,
            )
        ),
    }
)


class RejseplanenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configflow for Rejseplanen integration."""

    VERSION = 1
    MINOR_VERSION = 1

    @override
    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"stop": RejseplanenSubentryStopFlow}

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=CONFIG_SCHEMA,
                description_placeholders={"name": "Rejseplanen"},
            )

        errors: dict[str, str] = {}
        auth_key = user_input[CONF_API_KEY]
        api = Rejseplanen(
            auth_key=auth_key,
            session=async_get_clientsession(self.hass),
        )

        try:
            result = await api.validate_auth_key_async()
        except RejseplanenConnectionError, RejseplanenAPIError, OSError:
            errors["base"] = "cannot_connect"
        else:
            if not result:
                errors["base"] = "invalid_auth"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    CONFIG_SCHEMA, user_input
                ),
                errors=errors,
            )
        # Store the authentication key and name
        return self.async_create_entry(
            title="Rejseplanen",
            data={CONF_API_KEY: auth_key},
        )


class RejseplanenSubentryStopFlow(ConfigSubentryFlow):
    """Handle subentry flow for Rejseplanen stops."""

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Handle the stop subentry step."""

        if user_input is not None:
            stop_id = user_input[CONF_STOP_ID]
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
                    CONF_STOP_ID: int(stop_id),
                    CONF_NAME: name,
                    CONF_DEPARTURE_TYPE: departure_types,
                    CONF_DIRECTION: user_input.get(CONF_DIRECTION, []),
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_STOP_SCHEMA,
            description_placeholders={
                "documentation_url": "https://www.home-assistant.io/integrations/rejseplanen/"
            },
        )
