"""The bayesian component."""

import logging
from typing import Any
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ABOVE, CONF_BELOW, CONF_DEVICE_CLASS, CONF_ENTITY_ID, CONF_NAME, CONF_PLATFORM, CONF_STATE, CONF_UNIQUE_ID, CONF_VALUE_TEMPLATE, Platform
from homeassistant.core import HomeAssistant
from .const import CONF_OBSERVATIONS, CONF_P_GIVEN_F, CONF_P_GIVEN_T, CONF_PRIOR, CONF_PROBABILITY_THRESHOLD, CONF_TEMPLATE, CONF_TO_STATE, DEFAULT_NAME, DEFAULT_PROBABILITY_THRESHOLD, DOMAIN
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA

PLATFORMS = [Platform.BINARY_SENSOR]

_LOGGER = logging.getLogger(__name__) #TODO delete-me

NUMERIC_STATE_SCHEMA = vol.Schema(
    {
        CONF_PLATFORM: "numeric_state",
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_ABOVE): vol.Coerce(float),
        vol.Optional(CONF_BELOW): vol.Coerce(float),
        vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
        vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float),
    },
    required=True,
)

STATE_SCHEMA = vol.Schema(
    {
        CONF_PLATFORM: CONF_STATE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TO_STATE): cv.string,
        vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
        vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float),
    },
    required=True,
)

TEMPLATE_SCHEMA = vol.Schema(
    {
        CONF_PLATFORM: CONF_TEMPLATE,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
        vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float),
    },
    required=True,
)

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): cv.string,
        vol.Required(CONF_OBSERVATIONS): vol.Schema(
            vol.All(
                cv.ensure_list,
                [vol.Any(NUMERIC_STATE_SCHEMA, STATE_SCHEMA, TEMPLATE_SCHEMA)],
            )
        ),
        vol.Required(CONF_PRIOR): vol.Coerce(float),
        vol.Optional(
            CONF_PROBABILITY_THRESHOLD, default=DEFAULT_PROBABILITY_THRESHOLD
        ): vol.Coerce(float),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bayesian from a config entry."""

    _LOGGER.error(f"Config {entry.options}")#TODO Entries are coming through without Observations: list[dict]
    # but instead like 2024-08-05 19:58:22.241 ERROR (MainThread) [homeassistant.components.bayesian] Config {'name': 'Bayesian Binary Sensor', 'probability_threshold': 50.0, 'prior': 50.0, 'device_class': 'connectivity', 'entity_id': 'sensor.google_com', 'to_state': 'on', 'prob_given_true': 98.0, 'prob_given_false': 2.0}
    config: dict[str, Any] = PLATFORM_SCHEMA(dict(entry.options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
