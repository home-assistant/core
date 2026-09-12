"""Config flow for the Foreca integration."""

import logging
from typing import Any, override

from pyforeca import (
    ForecaApiClient,
    ForecaAuthError,
    ForecaError,
    Location,
    format_location,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_check_location(
    hass: HomeAssistant, api_key: str, latitude: float, longitude: float
) -> tuple[dict[str, str], Location | None]:
    """Check a key against a location, returning form errors if any."""
    client = ForecaApiClient(api_key, session=async_get_clientsession(hass))
    location = format_location(lon=longitude, lat=latitude)
    try:
        info = await client.location_info(location)
        await client.current(location)
    except ForecaAuthError:
        return {"base": "invalid_auth"}, None
    except ForecaError:
        return {"base": "cannot_connect"}, None
    except Exception:
        _LOGGER.exception("Unexpected error validating Foreca API key")
        return {"base": "unknown"}, None
    return {}, info


class ForecaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Foreca."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API key, and check it against the home location."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            errors, info = await _async_check_location(
                self.hass,
                user_input[CONF_API_KEY],
                self.hass.config.latitude,
                self.hass.config.longitude,
            )
            if not errors:
                return self.async_create_entry(
                    title="Foreca",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                    subentries=[
                        ConfigSubentryData(
                            data={
                                CONF_LATITUDE: self.hass.config.latitude,
                                CONF_LONGITUDE: self.hass.config.longitude,
                            },
                            subentry_type="location",
                            title=(info.name if info else None) or "Foreca",
                            unique_id=(
                                f"{self.hass.config.latitude}-"
                                f"{self.hass.config.longitude}"
                            ),
                        )
                    ],
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types this integration supports."""
        return {"location": LocationSubentryFlowHandler}


class LocationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a location to an existing Foreca entry."""

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Ask for a location to forecast."""
        errors: dict[str, str] = {}
        entry = self._get_entry()
        if user_input is not None:
            latitude = user_input[CONF_LOCATION][CONF_LATITUDE]
            longitude = user_input[CONF_LOCATION][CONF_LONGITUDE]
            unique = f"{latitude}-{longitude}"
            if any(
                subentry.unique_id == unique for subentry in entry.subentries.values()
            ):
                return self.async_abort(reason="already_configured")

            errors, info = await _async_check_location(
                self.hass, entry.data[CONF_API_KEY], latitude, longitude
            )
            if not errors:
                return self.async_create_entry(
                    title=(info.name if info else None) or "Foreca",
                    data={CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude},
                    unique_id=unique,
                )

        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATION,
                        default={
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                    ): LocationSelector()
                }
            ),
            errors=errors,
        )

    async_step_user = async_step_location
