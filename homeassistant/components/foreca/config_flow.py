"""Config flow for the Foreca integration."""

from collections.abc import Mapping
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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ForecaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Foreca."""

    async def _async_validate_key(
        self, api_key: str, latitude: float, longitude: float
    ) -> tuple[dict[str, str], Location | None]:
        """Check an API key against the location, returning form errors if any."""
        client = ForecaApiClient(api_key, session=async_get_clientsession(self.hass))
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

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            latitude = user_input[CONF_LOCATION][CONF_LATITUDE]
            longitude = user_input[CONF_LOCATION][CONF_LONGITUDE]
            errors, info = await self._async_validate_key(
                user_input[CONF_API_KEY], latitude, longitude
            )
            if not errors:
                await self.async_set_unique_id(f"{latitude:.4f}-{longitude:.4f}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=(info.name if info else None) or "Foreca",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_LATITUDE: latitude,
                        CONF_LONGITUDE: longitude,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(
                        CONF_LOCATION,
                        default={
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                    ): LocationSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle an API key the API has started rejecting."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a replacement API key."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors, _ = await self._async_validate_key(
                user_input[CONF_API_KEY],
                reauth_entry.data[CONF_LATITUDE],
                reauth_entry.data[CONF_LONGITUDE],
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            description_placeholders={"location": reauth_entry.title},
            errors=errors,
        )
