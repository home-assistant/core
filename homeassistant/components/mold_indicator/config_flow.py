"""Config flow for Mold Indicator integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import (
    CONF_CALIBRATION_FACTOR,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=mold_indicator"}
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INDOOR_TEMP): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=SENSOR_DOMAIN,
                filter=selector.EntityFilterSelectorConfig(
                    device_class=SensorDeviceClass.TEMPERATURE
                ),
            ),
        ),
        vol.Required(CONF_OUTDOOR_TEMP): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=SENSOR_DOMAIN,
                filter=selector.EntityFilterSelectorConfig(
                    device_class=SensorDeviceClass.TEMPERATURE
                ),
            ),
        ),
        vol.Required(CONF_INDOOR_HUMIDITY): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=SENSOR_DOMAIN,
                filter=selector.EntityFilterSelectorConfig(
                    device_class=SensorDeviceClass.HUMIDITY
                ),
            ),
        ),
        vol.Optional(CONF_CALIBRATION_FACTOR): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


class MoldIndicatorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mold Indicator."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_INDOOR_HUMIDITY: user_input[CONF_INDOOR_HUMIDITY],
                    CONF_INDOOR_TEMP: user_input[CONF_INDOOR_TEMP],
                    CONF_OUTDOOR_TEMP: user_input[CONF_OUTDOOR_TEMP],
                }
            )

            await self.async_set_unique_id(user_input[CONF_NAME])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Import the YAML config."""
        self._async_abort_entries_match(
            {
                CONF_INDOOR_HUMIDITY: user_input[CONF_INDOOR_HUMIDITY],
                CONF_INDOOR_TEMP: user_input[CONF_INDOOR_TEMP],
                CONF_OUTDOOR_TEMP: user_input[CONF_OUTDOOR_TEMP],
            }
        )

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Mold Indicator",
            },
        )

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
