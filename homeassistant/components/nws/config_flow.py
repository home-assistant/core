"""Config flow for National Weather Service (NWS) integration."""

import logging
from typing import Any, override

import aiohttp
import probatio
from pynws import SimpleNWS

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.location import get_state_coordinates
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    LocationSelector,
    LocationSelectorConfig,
)

from . import base_unique_id
from .const import CONF_LOCATION_ENTITY, CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    latitude = data[CONF_LOCATION][CONF_LATITUDE]
    longitude = data[CONF_LOCATION][CONF_LONGITUDE]
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

    VERSION = 2

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
            await self.async_set_unique_id(base_unique_id(**user_input[CONF_LOCATION]))
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

        data_schema = self.add_suggested_values_to_schema(
            probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                    probatio.Required(CONF_LOCATION): LocationSelector(
                        LocationSelectorConfig(radius=False)
                    ),
                    probatio.Optional(CONF_STATION): str,
                }
            ),
            user_input
            or {
                CONF_LOCATION: {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                }
            },
        )

        return self.async_show_form(
            step_id="location", data_schema=data_schema, errors=errors
        )

    async def async_step_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the entity-based configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None and (
            data := await self._async_validate_entity(user_input, errors)
        ):
            return self.async_create_entry(
                title=user_input[CONF_LOCATION_ENTITY], data=data
            )

        data_schema = probatio.Schema(
            {
                probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                probatio.Required(CONF_LOCATION_ENTITY): EntitySelector(
                    EntitySelectorConfig(
                        domain=["person", "device_tracker", "zone"],
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="entity", data_schema=data_schema, errors=errors
        )

    async def _async_validate_entity(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> dict[str, Any] | None:
        """Validate the entity input and return the entry data."""
        location_entity = user_input[CONF_LOCATION_ENTITY]

        registry = er.async_get(self.hass)
        entity_entry = registry.async_get(location_entity)
        if entity_entry is None:
            errors["base"] = "entity_not_found"
            return None
        if entity_entry.disabled_by is not None:
            errors["base"] = "entity_disabled"
            return None
        state = self.hass.states.get(location_entity)
        if state is None or (coordinates := get_state_coordinates(state)) is None:
            errors["base"] = "entity_no_coordinates"
            return None

        self._async_abort_entries_match({CONF_LOCATION_ENTITY: entity_entry.id})
        try:
            await validate_input(
                self.hass,
                {
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_LOCATION: {
                        CONF_LATITUDE: coordinates.latitude,
                        CONF_LONGITUDE: coordinates.longitude,
                    },
                },
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return {
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_LOCATION_ENTITY: entity_entry.id,
            }
        return None

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the API key and the station or entity."""
        entry = self._get_reconfigure_entry()
        if location_registry_id := entry.data.get(CONF_LOCATION_ENTITY):
            return await self._async_reconfigure_entity(
                user_input, location_registry_id
            )
        return await self._async_reconfigure_location(user_input)

    async def _async_reconfigure_location(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Reconfigure an entry for a specific location.

        The location is not reconfigurable as it is the unique ID of the entry.
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            try:
                info = await validate_input(
                    self.hass, {**user_input, CONF_LOCATION: entry.data[CONF_LOCATION]}
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_STATION: info["title"],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                        probatio.Optional(CONF_STATION): str,
                    }
                ),
                user_input or {CONF_STATION: entry.data[CONF_STATION]},
            ),
            errors=errors,
        )

    async def _async_reconfigure_entity(
        self, user_input: dict[str, Any] | None, location_registry_id: str
    ) -> ConfigFlowResult:
        """Reconfigure an entry that follows an entity."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None and (
            data := await self._async_validate_entity(user_input, errors)
        ):
            return self.async_update_reload_and_abort(entry, data_updates=data)

        suggested_values: dict[str, Any] = {}
        if entity_entry := er.async_get(self.hass).async_get(location_registry_id):
            suggested_values[CONF_LOCATION_ENTITY] = entity_entry.entity_id

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                        probatio.Required(CONF_LOCATION_ENTITY): EntitySelector(
                            EntitySelectorConfig(
                                domain=["person", "device_tracker", "zone"],
                            )
                        ),
                    }
                ),
                user_input or suggested_values,
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
