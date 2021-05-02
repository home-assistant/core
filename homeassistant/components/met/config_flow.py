"""Config flow to configure Met component."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_TRACK_HOME,
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DOMAIN,
    HOME_LOCATION_NAME,
)


@callback
def configured_instances(hass):
    """Return a set of configured SimpliSafe instances."""
    entries = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("track_home"):
            entries.append("home")
            continue
        entries.append(
            f"{entry.data.get(CONF_LATITUDE)}-{entry.data.get(CONF_LONGITUDE)}"
        )
    return set(entries)


class MetFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Met component."""

    VERSION = 1

    def __init__(self):
        """Init MetFlowHandler."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            if (
                f"{user_input.get(CONF_LATITUDE)}-{user_input.get(CONF_LONGITUDE)}"
                not in configured_instances(self.hass)
            ):
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            self._errors[CONF_NAME] = "already_configured"

        return await self._show_config_form(
            name=HOME_LOCATION_NAME,
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            elevation=self.hass.config.elevation,
        )

    async def _show_config_form(
        self, name=None, latitude=None, longitude=None, elevation=None
    ):
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=name): str,
                    vol.Required(CONF_LATITUDE, default=latitude): cv.latitude,
                    vol.Required(CONF_LONGITUDE, default=longitude): cv.longitude,
                    vol.Required(CONF_ELEVATION, default=elevation): int,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, user_input: dict | None = None) -> FlowResult:
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_onboarding(self, data=None):
        """Handle a flow initialized by onboarding."""
        # Don't create entry if latitude or longitude isn't set.
        # Also, filters out our onboarding default location.
        if (not self.hass.config.latitude and not self.hass.config.longitude) or (
            self.hass.config.latitude == DEFAULT_HOME_LATITUDE
            and self.hass.config.longitude == DEFAULT_HOME_LONGITUDE
        ):
            return self.async_abort(reason="no_home")

        return self.async_create_entry(
            title=HOME_LOCATION_NAME, data={CONF_TRACK_HOME: True}
        )
