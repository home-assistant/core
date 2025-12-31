"""Config flow for Forecast.Solar integration."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_AZIMUTH,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    CONF_PLANES,
    DOMAIN,
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

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ForecastSolarOptionFlowHandler:
        """Get the options flow for this handler."""
        return ForecastSolarOptionFlowHandler()

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
                options={
                    CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                    CONF_DECLINATION: user_input[CONF_DECLINATION],
                    CONF_MODULES_POWER: user_input[CONF_MODULES_POWER],
                },
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


class ForecastSolarOptionFlowHandler(OptionsFlowWithReload):
    """Handle options."""

    def _has_api_key(self) -> bool:
        """Check if an API key is configured."""
        api_key = self.config_entry.options.get(CONF_API_KEY)
        return api_key is not None and api_key != ""

    def _get_planes(self) -> list[dict[str, Any]]:
        """Get the list of additional planes."""
        planes: list[dict[str, Any]] = self.config_entry.options.get(CONF_PLANES, [])
        return planes

    def _get_plane_options(self) -> list[SelectOptionDict]:
        """Get plane options for the remove selector."""
        planes = self._get_planes()
        return [
            SelectOptionDict(
                value=str(i),
                label=f"Plane {i + 2}: {plane[CONF_DECLINATION]}° / {plane[CONF_AZIMUTH]}° / {plane[CONF_MODULES_POWER]}W",
            )
            for i, plane in enumerate(planes)
        ]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "add_plane", "remove_plane"],
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the main settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (api_key := user_input.get(CONF_API_KEY)) and RE_API_KEY.match(
                api_key
            ) is None:
                errors[CONF_API_KEY] = "invalid_api_key"
            else:
                # Preserve existing planes when updating settings
                new_options = user_input | {CONF_API_KEY: api_key or None}
                if CONF_PLANES in self.config_entry.options:
                    new_options[CONF_PLANES] = self.config_entry.options[CONF_PLANES]
                return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="settings",
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
                    vol.Required(
                        CONF_DECLINATION,
                        default=self.config_entry.options[CONF_DECLINATION],
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=90)),
                    vol.Required(
                        CONF_AZIMUTH,
                        default=self.config_entry.options.get(CONF_AZIMUTH),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=360)),
                    vol.Required(
                        CONF_MODULES_POWER,
                        default=self.config_entry.options[CONF_MODULES_POWER],
                    ): vol.All(vol.Coerce(int), vol.Range(min=1)),
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

    async def async_step_add_plane(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add an additional plane."""
        if not self._has_api_key():
            return self.async_abort(reason="api_key_required")

        planes = self._get_planes()
        # Forecast.Solar allows: 2 planes for Personal Plus, 3 for Professional, 4 for Professional Plus
        # We'll allow up to 3 additional planes (4 total including the main one)
        if len(planes) >= 3:
            return self.async_abort(reason="max_planes_reached")

        if user_input is not None:
            new_plane = {
                CONF_DECLINATION: user_input[CONF_DECLINATION],
                CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                CONF_MODULES_POWER: user_input[CONF_MODULES_POWER],
            }
            new_options = deepcopy({**self.config_entry.options})
            if CONF_PLANES not in new_options:
                new_options[CONF_PLANES] = []
            new_options[CONF_PLANES].append(new_plane)
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="add_plane",
            data_schema=_get_plane_schema(),
        )

    async def async_step_remove_plane(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove an additional plane."""
        planes = self._get_planes()

        if not planes:
            return self.async_abort(reason="no_planes_to_remove")

        if user_input is not None:
            # Get selected indices and sort in reverse order to remove from end first
            indices_to_remove = sorted(
                [int(idx) for idx in user_input["plane_indices"]], reverse=True
            )
            new_options = deepcopy({**self.config_entry.options})
            for plane_index in indices_to_remove:
                new_options[CONF_PLANES].pop(plane_index)
            if not new_options[CONF_PLANES]:
                del new_options[CONF_PLANES]
            return self.async_create_entry(title="", data=new_options)

        plane_options = self._get_plane_options()

        return self.async_show_form(
            step_id="remove_plane",
            data_schema=vol.Schema(
                {
                    vol.Required("plane_indices"): SelectSelector(
                        SelectSelectorConfig(
                            options=plane_options,
                            mode=SelectSelectorMode.LIST,
                            multiple=True,
                        )
                    ),
                }
            ),
        )
