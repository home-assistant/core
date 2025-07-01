"""Config flow for Rejseplanen integration."""

import hashlib
import json
from typing import Any

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
)

from .const import (
    BUS_TYPES,
    CONF_AUTHENTICATION,
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_NAME,
    CONF_ROUTE,
    CONF_STOP_ID,
    DEFAULT_STOP_NAME,
    DOMAIN,
    METRO_TYPES,
    TRAIN_TYPES,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTHENTICATION): str,
        vol.Required(CONF_NAME, default="Rejseplanen"): str,
    }
)

CONFIG_STOP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STOP_ID): NumberSelector(
            NumberSelectorConfig(
                mode=NumberSelectorMode.BOX, min=1, max=99999999, step=1
            ),
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_STOP_NAME): str,
        vol.Optional(
            CONF_DEPARTURE_TYPE,
            default=[],
        ): cv.multi_select(
            {
                **{bus_type: f"Bus {bus_type}" for bus_type in BUS_TYPES},
                **{train_type: f"Train {train_type}" for train_type in TRAIN_TYPES},
                **{metro_type: f"Metro {metro_type}" for metro_type in METRO_TYPES},
            }
        ),
    }
)


class RejseplanenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configflow for Rejseplanen integration."""

    VERSION = 1
    MINOR_VERSION = 0

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

        # Store the authentication key and name
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_AUTHENTICATION: auth_key,
                CONF_NAME: user_input[CONF_NAME],
                "is_main_entry": True,
            },
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

        unique_parts: dict[str, str | list[Any]] = {
            "route": user_input.get(CONF_ROUTE, []),
            "direction": user_input.get(CONF_DIRECTION, []),
            "departure_type": user_input.get(CONF_DEPARTURE_TYPE, []),
        }
        unique_str = json.dumps(unique_parts, sort_keys=True, separators=(",", ":"))
        unique_hash = hashlib.sha256(unique_str.encode()).hexdigest()[:8]
        unique_id = f"{stop_id}-{unique_hash}"

        return self.async_create_entry(
            title=name,
            data={
                CONF_STOP_ID: stop_id,
                CONF_NAME: name,
                CONF_DEPARTURE_TYPE: user_input.get(CONF_DEPARTURE_TYPE, []),
                CONF_DIRECTION: user_input.get(CONF_DIRECTION, []),
                CONF_ROUTE: user_input.get(CONF_ROUTE, []),
            },
            unique_id=unique_id,
        )
