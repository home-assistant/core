"""Config flow for Netatmo."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
import uuid

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_SHOW_ON_MAP, CONF_UUID
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from .api import get_api_scopes
from .const import (
    CONF_AREA_NAME,
    CONF_LAT_NE,
    CONF_LAT_SW,
    CONF_LON_NE,
    CONF_LON_SW,
    CONF_NEW_AREA,
    CONF_PUBLIC_MODE,
    CONF_WEATHER_AREAS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class NetatmoFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Netatmo OAuth2 authentication."""

    DOMAIN = DOMAIN

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return NetatmoOptionsFlowHandler(config_entry)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        scopes = get_api_scopes(self.flow_impl.domain)
        return {"scope": " ".join(scopes)}

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow start."""
        await self.async_set_unique_id(DOMAIN)

        if self.source != SOURCE_REAUTH and self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        existing_entry = await self.async_set_unique_id(DOMAIN)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return await super().async_oauth_create_entry(data)


class NetatmoOptionsFlowHandler(OptionsFlow):
    """Handle Netatmo options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Netatmo options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.options.setdefault(CONF_WEATHER_AREAS, {})

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Manage the Netatmo options."""
        return await self.async_step_public_weather_areas()

    async def async_step_public_weather_areas(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Manage configuration of Netatmo public weather areas."""
        errors: dict = {}

        if user_input is not None:
            new_client = user_input.pop(CONF_NEW_AREA, None)
            areas = user_input.pop(CONF_WEATHER_AREAS, [])
            user_input[CONF_WEATHER_AREAS] = {
                area: self.options[CONF_WEATHER_AREAS][area] for area in areas
            }
            self.options.update(user_input)
            if new_client:
                return await self.async_step_public_weather(
                    user_input={CONF_NEW_AREA: new_client}
                )

            return self._create_options_entry()

        weather_areas = list(self.options[CONF_WEATHER_AREAS])

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_WEATHER_AREAS,
                    default=weather_areas,
                ): cv.multi_select({wa: None for wa in weather_areas}),
                vol.Optional(CONF_NEW_AREA): str,
            }
        )
        return self.async_show_form(
            step_id="public_weather_areas",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_public_weather(self, user_input: dict) -> ConfigFlowResult:
        """Manage configuration of Netatmo public weather sensors."""
        if user_input is not None and CONF_NEW_AREA not in user_input:
            self.options[CONF_WEATHER_AREAS][user_input[CONF_AREA_NAME]] = (
                fix_coordinates(user_input)
            )

            self.options[CONF_WEATHER_AREAS][user_input[CONF_AREA_NAME]][CONF_UUID] = (
                str(uuid.uuid4())
            )

            return await self.async_step_public_weather_areas()

        orig_options = self.config_entry.options.get(CONF_WEATHER_AREAS, {}).get(
            user_input[CONF_NEW_AREA], {}
        )

        default_longitude = self.hass.config.longitude
        default_latitude = self.hass.config.latitude
        default_size = 0.04

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_AREA_NAME, default=user_input[CONF_NEW_AREA]): str,
                vol.Optional(
                    CONF_LAT_NE,
                    default=orig_options.get(
                        CONF_LAT_NE, default_latitude + default_size
                    ),
                ): cv.latitude,
                vol.Optional(
                    CONF_LON_NE,
                    default=orig_options.get(
                        CONF_LON_NE, default_longitude + default_size
                    ),
                ): cv.longitude,
                vol.Optional(
                    CONF_LAT_SW,
                    default=orig_options.get(
                        CONF_LAT_SW, default_latitude - default_size
                    ),
                ): cv.latitude,
                vol.Optional(
                    CONF_LON_SW,
                    default=orig_options.get(
                        CONF_LON_SW, default_longitude - default_size
                    ),
                ): cv.longitude,
                vol.Required(
                    CONF_PUBLIC_MODE,
                    default=orig_options.get(CONF_PUBLIC_MODE, "avg"),
                ): vol.In(["avg", "max"]),
                vol.Required(
                    CONF_SHOW_ON_MAP,
                    default=orig_options.get(CONF_SHOW_ON_MAP, False),
                ): bool,
            }
        )

        return self.async_show_form(step_id="public_weather", data_schema=data_schema)

    def _create_options_entry(self) -> ConfigFlowResult:
        """Update config entry options."""
        return self.async_create_entry(
            title="Netatmo Public Weather", data=self.options
        )


def fix_coordinates(user_input: dict) -> dict:
    """Fix coordinates if they don't comply with the Netatmo API."""
    # Ensure coordinates have acceptable length for the Netatmo API
    for coordinate in (CONF_LAT_NE, CONF_LAT_SW, CONF_LON_NE, CONF_LON_SW):
        if len(str(user_input[coordinate]).split(".")[1]) < 7:
            user_input[coordinate] = user_input[coordinate] + 0.0000001

    # Swap coordinates if entered in wrong order
    if user_input[CONF_LAT_NE] < user_input[CONF_LAT_SW]:
        user_input[CONF_LAT_NE], user_input[CONF_LAT_SW] = (
            user_input[CONF_LAT_SW],
            user_input[CONF_LAT_NE],
        )
    if user_input[CONF_LON_NE] < user_input[CONF_LON_SW]:
        user_input[CONF_LON_NE], user_input[CONF_LON_SW] = (
            user_input[CONF_LON_SW],
            user_input[CONF_LON_NE],
        )

    return user_input
