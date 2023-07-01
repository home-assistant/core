"""Adds config flow for Brottsplatskartan integration."""
from __future__ import annotations

from typing import Any
import uuid

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import AREAS, CONF_APP_ID, CONF_AREA, DEFAULT_NAME, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LOCATION): selector.LocationSelector(
            selector.LocationSelectorConfig(radius=False, icon="")
        ),
        vol.Optional(CONF_AREA, default="none"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=AREAS,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="areas",
            )
        ),
    }
)


class BPKConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brottsplatskartan integration."""

    VERSION = 1

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a configuration from config.yaml."""

        if config.get(CONF_LATITUDE):
            config[CONF_LOCATION] = {
                CONF_LATITUDE: config[CONF_LATITUDE],
                CONF_LONGITUDE: config[CONF_LONGITUDE],
            }
        if not config.get(CONF_AREA):
            config[CONF_AREA] = "none"
        else:
            config[CONF_AREA] = config[CONF_AREA][0]

        return await self.async_step_user(user_input=config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            latitude: float | None = None
            longitude: float | None = None
            area: str | None = (
                user_input[CONF_AREA] if user_input[CONF_AREA] != "none" else None
            )

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
