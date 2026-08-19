"""Config flow for National Weather Service (NWS) integration."""

import logging
from typing import Any, override

import aiohttp
from pynws import SimpleNWS
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.location import has_location
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from . import base_unique_id
from .const import CONF_LOCATION_ENTITY, CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    latitude = data[CONF_LATITUDE]
    longitude = data[CONF_LONGITUDE]
    api_key = data[CONF_API_KEY]
    station = data.get(CONF_STATION)

    client_session = async_get_clientsession(hass)
    ha_api_key = f"{api_key} homeassistant"
    nws = SimpleNWS(latitude, longitude, ha_api_key, client_session)

    try:
        await nws.set_station(station)
    except aiohttp.ClientError as err:
        _LOGGER.error("Could not connect: %s", err)
        raise CannotConnect from err

    return {"title": nws.station}


class NWSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for National Weather Service (NWS)."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step with menu selection."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["location", "entity"],
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the specific location configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                base_unique_id(user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE])
            )
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
                user_input[CONF_STATION] = info["title"]
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(CONF_STATION): str,
            }
        )

        return self.async_show_form(
            step_id="location", data_schema=data_schema, errors=errors
        )

    async def async_step_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the entity-based configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            location_entity = user_input[CONF_LOCATION_ENTITY]

            registry = er.async_get(self.hass)
            entity_entry = registry.async_get(location_entity)
            if entity_entry is None:
                errors["base"] = "entity_not_found"
            elif entity_entry.disabled_by is not None:
                errors["base"] = "entity_disabled"
            else:
                state = self.hass.states.get(location_entity)
                if state is None or not has_location(state):
                    errors["base"] = "entity_no_coordinates"
                else:
                    data = {
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_LOCATION_ENTITY: entity_entry.id,
                    }
                    self._async_abort_entries_match(
                        {CONF_LOCATION_ENTITY: entity_entry.id}
                    )
                    try:
                        await validate_input(
                            self.hass,
                            {
                                CONF_API_KEY: user_input[CONF_API_KEY],
                                CONF_LATITUDE: state.attributes[
                                    EntityStateAttribute.LATITUDE
                                ],
                                CONF_LONGITUDE: state.attributes[
                                    EntityStateAttribute.LONGITUDE
                                ],
                            },
                        )
                        return self.async_create_entry(title=location_entity, data=data)
                    except CannotConnect:
                        errors["base"] = "cannot_connect"
                    except Exception:
                        _LOGGER.exception("Unexpected exception")
                        errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_LOCATION_ENTITY): EntitySelector(
                    EntitySelectorConfig(
                        domain=["person", "device_tracker", "zone"],
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="entity", data_schema=data_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
