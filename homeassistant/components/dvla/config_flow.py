"""Config flow for DVLA integration."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.components.calendar import CalendarEntityFeature
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow as ConfigFlowBase,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_CALENDARS, CONF_REG_NUMBER, DOMAIN
from .coordinator import DVLACoordinator

_LOGGER = logging.getLogger(__name__)


async def _get_calendar_entities(hass: HomeAssistant) -> dict[str, str]:
    """Retrieve calendar entities."""
    entity_registry = er.async_get(hass)
    calendar_entities = {}
    for entity_id, entity in entity_registry.entities.items():
        if entity_id.startswith("calendar."):
            calendar_entity = hass.states.get(entity_id)
            if calendar_entity:
                supported_features = calendar_entity.attributes.get(
                    "supported_features", 0
                )

                supports_create_event = (
                    supported_features & CalendarEntityFeature.CREATE_EVENT
                )

                if supports_create_event:
                    calendar_name = entity.original_name or entity_id
                    calendar_entities[entity_id] = calendar_name

    calendar_entities["None"] = "Create a new calendar"
    return calendar_entities


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from step_user_data_schema with values provided by the user.
    """
    session = async_get_clientsession(hass)
    coordinator = DVLACoordinator(
        hass,
        None,
        session,
        user_input[CONF_REG_NUMBER],
    )

    await coordinator.async_refresh()

    if coordinator.last_exception is not None:
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": str(user_input[CONF_REG_NUMBER]).upper()}


class DVLAFlowHandler(OptionsFlow):
    """Handle a option flow for DVLA."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""

        calendar_entities = await _get_calendar_entities(self.hass)

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_CALENDARS,
                    default=self._config_entry.data.get(CONF_CALENDARS, []),
                ): cv.multi_select(calendar_entities),
            }
        )

        if user_input is not None:
            if not user_input.get(CONF_CALENDARS):
                return self.async_show_form(
                    step_id="init",
                    data_schema=options_schema,
                    errors={"base": "no_calendar_selected"},
                )

            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={**self._config_entry.data, **user_input},
                options=self._config_entry.options,
            )

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )


class ConfigFlow(ConfigFlowBase, domain=DOMAIN):
    """Handle a config flow for DVLA."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        calendar_entities = await _get_calendar_entities(self.hass)

        if user_input is None:
            user_input = {}

            step_user_data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_REG_NUMBER, default=user_input.get(CONF_REG_NUMBER, "")
                    ): cv.string,
                    vol.Required(
                        CONF_CALENDARS, default=user_input.get(CONF_CALENDARS, ["None"])
                    ): cv.multi_select(calendar_entities),
                }
            )

            return self.async_show_form(
                step_id="user",
                data_schema=step_user_data_schema,
                errors=errors,
            )

        reg_number = user_input[CONF_REG_NUMBER].replace(" ", "").upper()

        await self.async_set_unique_id(reg_number)
        self._abort_if_unique_id_configured()

        user_input[CONF_REG_NUMBER] = reg_number

        if user_input:
            entries = self.hass.config_entries.async_entries(DOMAIN)

            if any(
                entry.data.get(CONF_REG_NUMBER) == user_input.get(CONF_REG_NUMBER)
                for entry in entries
            ):
                errors["base"] = "vehicle_exists"

            if not user_input.get(CONF_CALENDARS):
                errors["base"] = "no_calendar_selected"

            if not errors:
                try:
                    info = await validate_input(self.hass, user_input)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=step_user_data_schema, errors=errors
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return DVLAFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
