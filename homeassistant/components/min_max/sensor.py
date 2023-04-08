"""Support for displaying minimal, maximal, mean or median values."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.group.sensor import SensorGroup
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ENTITY_IDS, CONF_ROUND_DIGITS, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_MIN_VALUE = "min_value"
ATTR_MIN_ENTITY_ID = "min_entity_id"
ATTR_MAX_VALUE = "max_value"
ATTR_MAX_ENTITY_ID = "max_entity_id"
ATTR_MEAN = "mean"
ATTR_MEDIAN = "median"
ATTR_LAST = "last"
ATTR_LAST_ENTITY_ID = "last_entity_id"
ATTR_RANGE = "range"
ATTR_SUM = "sum"

ICON = "mdi:calculator"

SENSOR_TYPES = {
    ATTR_MIN_VALUE: "min",
    ATTR_MAX_VALUE: "max",
    ATTR_MEAN: "mean",
    ATTR_MEDIAN: "median",
    ATTR_LAST: "last",
    ATTR_RANGE: "range",
    ATTR_SUM: "sum",
}
SENSOR_TYPE_TO_ATTR = {v: k for k, v in SENSOR_TYPES.items()}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TYPE, default=SENSOR_TYPES[ATTR_MAX_VALUE]): vol.All(
            cv.string, vol.In(SENSOR_TYPES.values())
        ),
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_IDS): cv.entity_ids,
        vol.Optional(CONF_ROUND_DIGITS, default=2): vol.Coerce(int),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize min/max/mean config entry."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_integration",
        breaks_in_ha_version="2023.5.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_integration",
    )

    import_config = {
        "ignore_non_numeric": False,
        "entities": config_entry.options[CONF_ENTITY_IDS],
        "hide_members": False,
        "type": config_entry.options[CONF_TYPE],
        "name": f"Sensor Group {config_entry.options[CONF_NAME]}",
    }

    await hass.async_create_task(
        hass.config_entries.flow.async_init(
            "group",
            context={"source": SOURCE_IMPORT},
            data=import_config,
        )
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the min/max/mean sensor."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_integration",
        breaks_in_ha_version="2023.4.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_integration_yaml",
    )

    entity_ids: list[str] = config[CONF_ENTITY_IDS]
    name: str | None = config.get(CONF_NAME)
    sensor_type: str = config[CONF_TYPE]
    unique_id = config.get(CONF_UNIQUE_ID)

    import_config = {
        "ignore_non_numeric": False,
        "entities": entity_ids,
        "hide_members": False,
        "type": sensor_type,
        "name": f"Sensor Group {name}"
        if name
        else f"Sensor Group {sensor_type}".capitalize(),
    }

    await hass.async_create_task(
        hass.config_entries.flow.async_init(
            "group",
            context={"source": SOURCE_IMPORT},
            data=import_config,
        )
    )

    async_add_entities(
        [
            SensorGroup(
                unique_id,
                name if name else f"{sensor_type} sensor".capitalize(),
                entity_ids,
                False,
                sensor_type,
                None,
                None,
                None,
            )
        ]
    )
