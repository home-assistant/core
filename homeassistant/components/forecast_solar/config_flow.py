"""Config flow for Forecast.Solar integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_AZIMUTH,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DOMAIN,
    MAX_PLANES,
    SUBENTRY_TYPE_PLANE,
)

RE_API_KEY = re.compile(r"^[a-zA-Z0-9]{16}$")


def _get_plane_schema(
    declination: int = 25,
    azimuth: int = 180,
    modules_power: int | None = None,
) -> vol.Schema:
    """Get schema for plane configuration."""
    schema: dict[Any, Any] = {
        vol.Required(CONF_DECLINATION, default=declination): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=90)
        ),
        vol.Required(CONF_AZIMUTH, default=azimuth): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=360)
        ),
    }
    if modules_power is not None:
        schema[vol.Required(CONF_MODULES_POWER, default=modules_power)] = vol.All(
            vol.Coerce(int), vol.Range(min=1)
        )
    else:
        schema[vol.Required(CONF_MODULES_POWER)] = vol.All(
            vol.Coerce(int), vol.Range(min=1)
        )
    return vol.Schema(schema)


class ForecastSolarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Forecast.Solar."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ForecastSolarOptionFlowHandler:
        """Get the options flow for this handler."""
        return ForecastSolarOptionFlowHandler()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_PLANE: PlaneSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                },
                subentries=[
                    {
                        "subentry_type": SUBENTRY_TYPE_PLANE,
                        "data": {
                            CONF_DECLINATION: user_input[CONF_DECLINATION],
                            CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                            CONF_MODULES_POWER: user_input[CONF_MODULES_POWER],
                        },
                        "title": f"{user_input[CONF_DECLINATION]}° / {user_input[CONF_AZIMUTH]}° / {user_input[CONF_MODULES_POWER]}W",
                        "unique_id": None,
                    },
                ],
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                    vol.Required(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Required(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                    vol.Required(CONF_DECLINATION, default=25): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=90)
                    ),
                    vol.Required(CONF_AZIMUTH, default=180): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=360)
                    ),
                    vol.Required(CONF_MODULES_POWER): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                }
            ),
        )


class ForecastSolarOptionFlowHandler(OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (api_key := user_input.get(CONF_API_KEY)) and RE_API_KEY.match(
                api_key
            ) is None:
                errors[CONF_API_KEY] = "invalid_api_key"
            else:
                return self.async_create_entry(
                    title="", data=user_input | {CONF_API_KEY: api_key or None}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_API_KEY,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_API_KEY, ""
                            )
                        },
                    ): str,
                    vol.Optional(
                        CONF_DAMPING_MORNING,
                        default=self.config_entry.options.get(
                            CONF_DAMPING_MORNING, 0.0
                        ),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_DAMPING_EVENING,
                        default=self.config_entry.options.get(
                            CONF_DAMPING_EVENING, 0.0
                        ),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_INVERTER_SIZE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_INVERTER_SIZE
                            )
                        },
                    ): vol.Coerce(int),
                }
            ),
            errors=errors,
        )


class PlaneSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding/editing a plane."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step to add a new plane."""
        entry = self._get_entry()
        plane_count = sum(
            1
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_PLANE
        )
        if plane_count >= MAX_PLANES:
            return self.async_abort(reason="max_planes")
        if plane_count >= 1 and not entry.options.get(CONF_API_KEY):
            return self.async_abort(reason="api_key_required")

        if user_input is not None:
            return self.async_create_entry(
                title=f"{user_input[CONF_DECLINATION]}° / {user_input[CONF_AZIMUTH]}° / {user_input[CONF_MODULES_POWER]}W",
                data={
                    CONF_DECLINATION: user_input[CONF_DECLINATION],
                    CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                    CONF_MODULES_POWER: user_input[CONF_MODULES_POWER],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_get_plane_schema(),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of an existing plane."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_entry(),
                subentry,
                data={
                    CONF_DECLINATION: user_input[CONF_DECLINATION],
                    CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                    CONF_MODULES_POWER: user_input[CONF_MODULES_POWER],
                },
                title=f"{user_input[CONF_DECLINATION]}° / {user_input[CONF_AZIMUTH]}° / {user_input[CONF_MODULES_POWER]}W",
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_get_plane_schema(
                declination=subentry.data[CONF_DECLINATION],
                azimuth=subentry.data[CONF_AZIMUTH],
                modules_power=subentry.data[CONF_MODULES_POWER],
            ),
        )
