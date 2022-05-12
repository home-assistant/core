"""Config flow to configure SMHI component."""
from __future__ import annotations

from typing import Any

from smhi.smhi_lib import Smhi, SmhiForecastException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv

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


class SmhiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for SMHI component."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}

        if user_input is not None:
            lat: float = user_input[CONF_LATITUDE]
            lon: float = user_input[CONF_LONGITUDE]
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

        default_lat: float = self.hass.config.latitude
        default_lon: float = self.hass.config.longitude

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if (
                entry.data[CONF_LATITUDE] == self.hass.config.latitude
                and entry.data[CONF_LONGITUDE] == self.hass.config.longitude
            ):
                default_lat = 0
                default_lon = 0

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LATITUDE, default=default_lat): cv.latitude,
                    vol.Required(CONF_LONGITUDE, default=default_lon): cv.longitude,
                }
            ),
            errors=errors,
        )
