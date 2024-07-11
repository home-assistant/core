"""Config flow to configure SMHI component."""

from __future__ import annotations

from typing import Any

from smhi.smhi_lib import Smhi, SmhiForecastException
import voluptuous as vol

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.selector import LocationSelector

from .const import DEFAULT_NAME, DOMAIN, HOME_LOCATION_NAME


async def async_check_location(
    hass: HomeAssistant, longitude: float, latitude: float
) -> bool:
    """Return true if location is ok."""
    session = aiohttp_client.async_get_clientsession(hass)
    smhi_api = Smhi(longitude, latitude, session=session)
    try:
        await smhi_api.async_get_forecast()
    except SmhiForecastException:
        return False

    return True


class SmhiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for SMHI component."""

    VERSION = 2
    config_entry: ConfigEntry | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}

        if user_input is not None:
            lat: float = user_input[CONF_LOCATION][CONF_LATITUDE]
            lon: float = user_input[CONF_LOCATION][CONF_LONGITUDE]
            if await async_check_location(self.hass, lon, lat):
                name = f"{DEFAULT_NAME} {round(lat, 6)} {round(lon, 6)}"
                if (
                    lat == self.hass.config.latitude
                    and lon == self.hass.config.longitude
                ):
                    name = HOME_LOCATION_NAME

                user_input[CONF_NAME] = (
                    HOME_LOCATION_NAME if name == HOME_LOCATION_NAME else DEFAULT_NAME
                )

                await self.async_set_unique_id(f"{lat}-{lon}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=name, data=user_input)

            errors["base"] = "wrong_location"

        home_location = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_LOCATION, default=home_location): LocationSelector()}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors: dict[str, str] = {}
        assert self.config_entry

        if user_input is not None:
            lat: float = user_input[CONF_LOCATION][CONF_LATITUDE]
            lon: float = user_input[CONF_LOCATION][CONF_LONGITUDE]
            if await async_check_location(self.hass, lon, lat):
                unique_id = f"{lat}-{lon}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                old_lat = self.config_entry.data[CONF_LOCATION][CONF_LATITUDE]
                old_lon = self.config_entry.data[CONF_LOCATION][CONF_LONGITUDE]

                entity_reg = er.async_get(self.hass)
                if entity := entity_reg.async_get_entity_id(
                    WEATHER_DOMAIN, DOMAIN, f"{old_lat}, {old_lon}"
                ):
                    entity_reg.async_update_entity(
                        entity, new_unique_id=f"{lat}, {lon}"
                    )

                device_reg = dr.async_get(self.hass)
                if device := device_reg.async_get_device(
                    identifiers={(DOMAIN, f"{old_lat}, {old_lon}")}
                ):
                    device_reg.async_update_device(
                        device.id, new_identifiers={(DOMAIN, f"{lat}, {lon}")}
                    )

                return self.async_update_reload_and_abort(
                    self.config_entry,
                    unique_id=unique_id,
                    data={**self.config_entry.data, **user_input},
                    reason="reconfigure_successful",
                )
            errors["base"] = "wrong_location"

        schema = self.add_suggested_values_to_schema(
            vol.Schema({vol.Required(CONF_LOCATION): LocationSelector()}),
            self.config_entry.data,
        )
        return self.async_show_form(
            step_id="reconfigure_confirm", data_schema=schema, errors=errors
        )
