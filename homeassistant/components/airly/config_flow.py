"""Adds config flow for Airly."""
from __future__ import annotations

from typing import Any

from aiohttp import ClientSession
from airly import Airly
from airly.exceptions import AirlyError
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    HTTP_NOT_FOUND,
    HTTP_UNAUTHORIZED,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_USE_NEAREST, DOMAIN, NO_AIRLY_SENSORS


class AirlyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Airly."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        use_nearest = False

        websession = async_get_clientsession(self.hass)

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_LATITUDE]}-{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()
            try:
                location_point_valid = await test_location(
                    websession,
                    user_input["api_key"],
                    user_input["latitude"],
                    user_input["longitude"],
                )
                if not location_point_valid:
                    await test_location(
                        websession,
                        user_input["api_key"],
                        user_input["latitude"],
                        user_input["longitude"],
                        use_nearest=True,
                    )
            except AirlyError as err:
                if err.status_code == HTTP_UNAUTHORIZED:
                    errors["base"] = "invalid_api_key"
                if err.status_code == HTTP_NOT_FOUND:
                    errors["base"] = "wrong_location"
            else:
                if not location_point_valid:
                    use_nearest = True
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={**user_input, CONF_USE_NEAREST: use_nearest},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                    vol.Optional(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                }
            ),
            errors=errors,
        )


async def test_location(
    client: ClientSession,
    api_key: str,
    latitude: float,
    longitude: float,
    use_nearest: bool = False,
) -> bool:
    """Return true if location is valid."""
    airly = Airly(api_key, client)
    if use_nearest:
        measurements = airly.create_measurements_session_nearest(
            latitude=latitude, longitude=longitude, max_distance_km=5
        )
    else:
        measurements = airly.create_measurements_session_point(
            latitude=latitude, longitude=longitude
        )
    with async_timeout.timeout(10):
        await measurements.update()

    current = measurements.current

    if current["indexes"][0]["description"] == NO_AIRLY_SENSORS:
        return False
    return True
