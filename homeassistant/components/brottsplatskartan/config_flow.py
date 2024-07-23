"""Adds config flow for Brottsplatskartan integration."""

from __future__ import annotations

from typing import Any
import uuid

from brottsplatskartan import AREAS
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.helpers import selector

from .const import CONF_APP_ID, CONF_AREA, DEFAULT_NAME, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LOCATION): selector.LocationSelector(
            selector.LocationSelectorConfig(radius=False, icon="")
        ),
        vol.Optional(CONF_AREA): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=AREAS,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


class BPKConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brottsplatskartan integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            latitude: float | None = None
            longitude: float | None = None
            area: str | None = user_input.get(CONF_AREA)

            if area:
                name = f"{DEFAULT_NAME} {area}"
            elif location := user_input.get(CONF_LOCATION):
                lat: float = location[CONF_LATITUDE]
                long: float = location[CONF_LONGITUDE]
                latitude = lat
                longitude = long
                name = f"{DEFAULT_NAME} {round(latitude, 2)}, {round(longitude, 2)}"
            else:
                latitude = self.hass.config.latitude
                longitude = self.hass.config.longitude
                name = f"{DEFAULT_NAME} HOME"

            app = f"ha-{uuid.getnode()}"

            self._async_abort_entries_match(
                {CONF_AREA: area, CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude}
            )
            return self.async_create_entry(
                title=name,
                data={
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                    CONF_AREA: area,
                    CONF_APP_ID: app,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
