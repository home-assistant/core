"""Config flow for Environment Canada integration."""

import logging
from typing import Any, override
import xml.etree.ElementTree as ET

import aiohttp
from env_canada import ECWeather, ec_exc
from env_canada.ec_weather import get_ec_sites_list
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_RADAR_DURATION,
    CONF_RADAR_FPS,
    CONF_RADAR_LAYER,
    CONF_RADAR_LEGEND,
    CONF_RADAR_OPACITY,
    CONF_RADAR_RADIUS,
    CONF_RADAR_TIMESTAMP,
    CONF_STATION,
    CONF_TITLE,
    DEFAULT_RADAR_DURATION,
    DEFAULT_RADAR_FPS,
    DEFAULT_RADAR_LAYER,
    DEFAULT_RADAR_LEGEND,
    DEFAULT_RADAR_OPACITY,
    DEFAULT_RADAR_RADIUS,
    DEFAULT_RADAR_TIMESTAMP,
    DOMAIN,
    RADAR_LAYERS,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(data):
    """Validate the user input allows us to connect."""
    lat = data.get(CONF_LATITUDE)
    lon = data.get(CONF_LONGITUDE)
    station = data.get(CONF_STATION)
    lang = data.get(CONF_LANGUAGE).lower()

    if station:
        # When station is provided, use it and get the coordinates from ECWeather
        weather_data = ECWeather(station_id=station, language=lang)
        await weather_data.update()
        # Always use the station's coordinates, not the user-provided ones
        lat = weather_data.lat
        lon = weather_data.lon
    else:
        # When no station is provided, use coordinates to find nearest station
        weather_data = ECWeather(coordinates=(lat, lon), language=lang)
        await weather_data.update()

    return {
        CONF_TITLE: weather_data.metadata.location,
        CONF_STATION: weather_data.station_id,
        CONF_LATITUDE: lat,
        CONF_LONGITUDE: lon,
    }


class EnvironmentCanadaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Environment Canada weather."""

    VERSION = 1
    _station_codes: list[dict[str, str]] | None = None

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Return the options flow handler."""
        return OptionsFlowHandler()

    async def _get_station_codes(self) -> list[dict[str, str]]:
        """Get station codes, cached after first call."""
        if self._station_codes is None:
            self._station_codes = await get_ec_sites_list()
        return self._station_codes

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(user_input)
            except ET.ParseError, vol.MultipleInvalid, ec_exc.UnknownStationId:
                errors["base"] = "bad_station_id"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except aiohttp.ClientResponseError as err:
                if err.status == 404:
                    errors["base"] = "bad_station_id"
                else:
                    errors["base"] = "error_response"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                user_input[CONF_STATION] = info[CONF_STATION]
                user_input[CONF_LATITUDE] = info[CONF_LATITUDE]
                user_input[CONF_LONGITUDE] = info[CONF_LONGITUDE]

                # The combination of station and language are
                # unique for all EC weather reporting
                await self.async_set_unique_id(
                    f"{user_input[CONF_STATION]}-{user_input[CONF_LANGUAGE].lower()}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info[CONF_TITLE], data=user_input)

        station_codes = await self._get_station_codes()

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_STATION): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=station["value"], label=station["label"]
                            )
                            for station in station_codes
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Required(CONF_LANGUAGE, default="English"): vol.In(
                    ["English", "French"]
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle Environment Canada radar camera options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the radar camera options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_RADAR_LAYER,
                    default=options.get(CONF_RADAR_LAYER, DEFAULT_RADAR_LAYER),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=RADAR_LAYERS,
                        translation_key="radar_layer",
                    )
                ),
                vol.Required(
                    CONF_RADAR_LEGEND,
                    default=options.get(CONF_RADAR_LEGEND, DEFAULT_RADAR_LEGEND),
                ): BooleanSelector(),
                vol.Required(
                    CONF_RADAR_TIMESTAMP,
                    default=options.get(CONF_RADAR_TIMESTAMP, DEFAULT_RADAR_TIMESTAMP),
                ): BooleanSelector(),
                vol.Required(
                    CONF_RADAR_OPACITY,
                    default=options.get(CONF_RADAR_OPACITY, DEFAULT_RADAR_OPACITY),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=100, step=1, mode=NumberSelectorMode.SLIDER
                    )
                ),
                vol.Required(
                    CONF_RADAR_RADIUS,
                    default=options.get(CONF_RADAR_RADIUS, DEFAULT_RADAR_RADIUS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10, max=2000, step=10, unit_of_measurement="km"
                    )
                ),
                vol.Required(
                    CONF_RADAR_DURATION,
                    default=options.get(CONF_RADAR_DURATION, DEFAULT_RADAR_DURATION),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=180, step=5, unit_of_measurement="min"
                    )
                ),
                vol.Required(
                    CONF_RADAR_FPS,
                    default=options.get(CONF_RADAR_FPS, DEFAULT_RADAR_FPS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=30, step=1, unit_of_measurement="fps"
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
