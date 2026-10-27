"""Adds config flow for Airly."""

from asyncio import timeout
from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any, override

from aiohttp import ClientConnectorError
from airly import Airly
from airly.exceptions import AirlyError
import probatio

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import (
    CONF_USE_NEAREST,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
    NO_AIRLY_SENSORS,
)

DESCRIPTION_PLACEHOLDERS = {
    "developer_registration_url": "https://developer.airly.eu/register",
}
_LOGGER = logging.getLogger(__name__)


class AirlyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Airly."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        use_nearest = False

        if user_input is not None:
            location: dict[str, Any] = user_input[CONF_LOCATION]
            await self.async_set_unique_id(
                f"{location[CONF_LATITUDE]}-{location[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            location_valid, errors = await self.async_check_location(
                user_input[CONF_API_KEY],
                location[CONF_LATITUDE],
                location[CONF_LONGITUDE],
            )
            if not location_valid and not errors:
                location_valid, errors = await self.async_check_location(
                    user_input[CONF_API_KEY],
                    location[CONF_LATITUDE],
                    location[CONF_LONGITUDE],
                    use_nearest=True,
                )
                use_nearest = location_valid

            if not errors:
                if not location_valid:
                    return self.async_abort(reason="wrong_location")
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_LATITUDE: location[CONF_LATITUDE],
                        CONF_LONGITUDE: location[CONF_LONGITUDE],
                        CONF_USE_NEAREST: use_nearest,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                        probatio.Required(CONF_LOCATION): LocationSelector(
                            LocationSelectorConfig(radius=False)
                        ),
                    }
                ),
                user_input
                or {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    }
                },
            ),
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        return await self._async_update_api_key(
            "reauth_confirm", self._get_reauth_entry(), user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self._async_update_api_key(
            "reconfigure", self._get_reconfigure_entry(), user_input
        )

    async def _async_update_api_key(
        self, step_id: str, entry: ConfigEntry, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Validate a new API key against the entry's location and update the entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _, errors = await self.async_check_location(
                user_input[CONF_API_KEY],
                entry.data[CONF_LATITUDE],
                entry.data[CONF_LONGITUDE],
                use_nearest=entry.data.get(CONF_USE_NEAREST, False),
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
            ),
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
        )

    async def async_check_location(
        self,
        api_key: str,
        latitude: float,
        longitude: float,
        use_nearest: bool = False,
    ) -> tuple[bool, dict[str, str]]:
        """Check the location and return its validity along with flow errors."""
        websession = async_get_clientsession(self.hass)
        airly = Airly(api_key, websession)

        if use_nearest:
            measurements = airly.create_measurements_session_nearest(
                latitude=latitude, longitude=longitude, max_distance_km=5
            )
        else:
            measurements = airly.create_measurements_session_point(
                latitude=latitude, longitude=longitude
            )

        try:
            async with timeout(DEFAULT_TIMEOUT):
                await measurements.update()
        except AirlyError as err:
            if err.status_code == HTTPStatus.UNAUTHORIZED:
                return False, {"base": "invalid_api_key"}
            if err.status_code == HTTPStatus.NOT_FOUND:
                return False, {"base": "wrong_location"}
            return False, {"base": "unknown"}
        except ClientConnectorError, TimeoutError:
            return False, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return False, {"base": "unknown"}

        location_valid = (
            measurements.current["indexes"][0]["description"] != NO_AIRLY_SENSORS
        )

        return location_valid, {}
