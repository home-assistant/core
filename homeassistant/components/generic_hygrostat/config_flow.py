"""Config flow for Generic Hygrostat integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from voluptuous.schema_builder import UNDEFINED

from homeassistant import config_entries
from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_AWAY_FIXED,
    CONF_AWAY_HUMIDITY,
    CONF_DEVICE_CLASS,
    CONF_DRY_TOLERANCE,
    CONF_HUMIDIFIER,
    CONF_INITIAL_STATE,
    CONF_KEEP_ALIVE,
    CONF_MAX_HUMIDITY,
    CONF_MIN_DUR,
    CONF_MIN_HUMIDITY,
    CONF_SENSOR,
    CONF_STALE_DURATION,
    CONF_TARGET_HUMIDITY,
    CONF_WET_TOLERANCE,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_DUR,
    DEFAULT_MIN_HUMIDITY,
    DEFAULT_NAME,
    DEFAULT_TOLERANCE,
    DOMAIN,
)


def generate_schema(existing_data: Mapping[str, str]):
    """Create schema for hygrostat config setup."""
    return vol.Schema(
        {
            vol.Required(
                CONF_HUMIDIFIER, default=existing_data.get(CONF_HUMIDIFIER, "")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch", multiple=False),
            ),
            vol.Required(
                CONF_SENSOR, default=existing_data.get(CONF_SENSOR, "")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=False),
            ),
            vol.Required(
                CONF_DEVICE_CLASS,
                default=existing_data.get(
                    CONF_DEVICE_CLASS, HumidifierDeviceClass.HUMIDIFIER
                ),
            ): vol.In(
                [HumidifierDeviceClass.HUMIDIFIER, HumidifierDeviceClass.DEHUMIDIFIER]
            ),
            vol.Optional(
                CONF_MIN_HUMIDITY,
                default=existing_data.get(CONF_MIN_HUMIDITY, DEFAULT_MIN_HUMIDITY),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_MAX_HUMIDITY,
                default=existing_data.get(CONF_MAX_HUMIDITY, DEFAULT_MAX_HUMIDITY),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_MIN_DUR, default=existing_data.get(CONF_MIN_DUR, DEFAULT_MIN_DUR)
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional(
                CONF_NAME, default=existing_data.get(CONF_NAME, DEFAULT_NAME)
            ): cv.string,
            vol.Optional(
                CONF_DRY_TOLERANCE,
                default=existing_data.get(CONF_DRY_TOLERANCE, DEFAULT_TOLERANCE),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_WET_TOLERANCE,
                default=existing_data.get(CONF_WET_TOLERANCE, DEFAULT_TOLERANCE),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_TARGET_HUMIDITY,
                default=existing_data.get(CONF_TARGET_HUMIDITY, UNDEFINED),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_KEEP_ALIVE, default=existing_data.get(CONF_KEEP_ALIVE, UNDEFINED)
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional(
                CONF_INITIAL_STATE, default=existing_data.get(CONF_INITIAL_STATE, False)
            ): cv.boolean,
            vol.Optional(
                CONF_AWAY_HUMIDITY,
                default=existing_data.get(CONF_AWAY_HUMIDITY, UNDEFINED),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_AWAY_FIXED, default=existing_data.get(CONF_AWAY_FIXED, False)
            ): cv.boolean,
            vol.Optional(
                CONF_STALE_DURATION,
                default=existing_data.get(CONF_STALE_DURATION, UNDEFINED),
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a Generic Hygrostat."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        errors: dict[str, str] = {}

        if user_input is None:
            user_input = {}
        else:
            pass

        return self.async_show_form(
            step_id="user",
            data_schema=generate_schema(user_input),
            errors=errors,
        )
