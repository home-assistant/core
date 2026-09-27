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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
            await self.async_set_unique_id(
                f"{user_input[CONF_LATITUDE]}-{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            location_valid, errors = await self.async_check_location(
                user_input[CONF_API_KEY],
                user_input[CONF_LATITUDE],
                user_input[CONF_LONGITUDE],
            )
            if not location_valid and not errors:
                location_valid, errors = await self.async_check_location(
                    user_input[CONF_API_KEY],
                    user_input[CONF_LATITUDE],
                    user_input[CONF_LONGITUDE],
                    use_nearest=True,
                )
                use_nearest = location_valid

            if not errors:
                if not location_valid:
                    return self.async_abort(reason="wrong_location")
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={**user_input, CONF_USE_NEAREST: use_nearest},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_API_KEY): str,
                    probatio.Optional(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    probatio.Optional(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                }
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
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            _, errors = await self.async_check_location(
                user_input[CONF_API_KEY],
                reauth_entry.data[CONF_LATITUDE],
                reauth_entry.data[CONF_LONGITUDE],
                use_nearest=reauth_entry.data.get(CONF_USE_NEAREST, False),
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema({probatio.Required(CONF_API_KEY): str}),
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
