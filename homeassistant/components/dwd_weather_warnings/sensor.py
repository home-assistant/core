"""
Support for getting statistical data from a DWD Weather Warnings.

Data is fetched from DWD:
https://rcccm.dwd.de/DE/wetter/warnungen_aktuell/objekt_einbindung/objekteinbindung.html

Warnungen vor extremem Unwetter (Stufe 4)
Unwetterwarnungen (Stufe 3)
Warnungen vor markantem Wetter (Stufe 2)
Wetterwarnungen (Stufe 1)
"""
from __future__ import annotations

from datetime import timedelta
import logging

from dwdwfsapi import DwdWeatherWarningsAPI
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_REGION_NAME = "region_name"
ATTR_REGION_ID = "region_id"
ATTR_LAST_UPDATE = "last_update"
ATTR_WARNING_COUNT = "warning_count"

API_ATTR_WARNING_NAME = "event"
API_ATTR_WARNING_TYPE = "event_code"
API_ATTR_WARNING_LEVEL = "level"
API_ATTR_WARNING_HEADLINE = "headline"
API_ATTR_WARNING_DESCRIPTION = "description"
API_ATTR_WARNING_INSTRUCTION = "instruction"
API_ATTR_WARNING_START = "start_time"
API_ATTR_WARNING_END = "end_time"
API_ATTR_WARNING_PARAMETERS = "parameters"
API_ATTR_WARNING_COLOR = "color"

DEFAULT_NAME = "DWD-Weather-Warnings"

CONF_REGION_NAME = "region_name"

CURRENT_WARNING_SENSOR = "current_warning_level"
ADVANCE_WARNING_SENSOR = "advance_warning_level"

SCAN_INTERVAL = timedelta(minutes=15)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CURRENT_WARNING_SENSOR,
        name="Current Warning Level",
        icon="mdi:close-octagon-outline",
    ),
    SensorEntityDescription(
        key=ADVANCE_WARNING_SENSOR,
        name="Advance Warning Level",
        icon="mdi:close-octagon-outline",
    ),
)
MONITORED_CONDITIONS: list[str] = [desc.key for desc in SENSOR_TYPES]


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_REGION_NAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=list(MONITORED_CONDITIONS)
        ): vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the DWD-Weather-Warnings sensor."""
    name = config.get(CONF_NAME)
    region_name = config.get(CONF_REGION_NAME)

    api = WrappedDwDWWAPI(DwdWeatherWarningsAPI(region_name))

    sensors = [
        DwdWeatherWarningsSensor(api, name, description)
        for description in SENSOR_TYPES
        if description.key in config[CONF_MONITORED_CONDITIONS]
    ]

    add_entities(sensors, True)


class DwdWeatherWarningsSensor(SensorEntity):
    """Representation of a DWD-Weather-Warnings sensor."""

    _attr_attribution = "Data provided by DWD"

    def __init__(
        self,
        api,
        name,
        description: SensorEntityDescription,
    ):
        """Initialize a DWD-Weather-Warnings sensor."""
        self._api = api
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.entity_description.key == CURRENT_WARNING_SENSOR:
            return self._api.api.current_warning_level
        return self._api.api.expected_warning_level

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the DWD-Weather-Warnings."""
        data = {
            ATTR_REGION_NAME: self._api.api.warncell_name,
            ATTR_REGION_ID: self._api.api.warncell_id,
            ATTR_LAST_UPDATE: self._api.api.last_update,
        }

        if self.entity_description.key == CURRENT_WARNING_SENSOR:
            searched_warnings = self._api.api.current_warnings
        else:
            searched_warnings = self._api.api.expected_warnings

        data[ATTR_WARNING_COUNT] = len(searched_warnings)

        for i, warning in enumerate(searched_warnings, 1):
            data[f"warning_{i}_name"] = warning[API_ATTR_WARNING_NAME]
            data[f"warning_{i}_type"] = warning[API_ATTR_WARNING_TYPE]
            data[f"warning_{i}_level"] = warning[API_ATTR_WARNING_LEVEL]
            data[f"warning_{i}_headline"] = warning[API_ATTR_WARNING_HEADLINE]
            data[f"warning_{i}_description"] = warning[API_ATTR_WARNING_DESCRIPTION]
            data[f"warning_{i}_instruction"] = warning[API_ATTR_WARNING_INSTRUCTION]
            data[f"warning_{i}_start"] = warning[API_ATTR_WARNING_START]
            data[f"warning_{i}_end"] = warning[API_ATTR_WARNING_END]
            data[f"warning_{i}_parameters"] = warning[API_ATTR_WARNING_PARAMETERS]
            data[f"warning_{i}_color"] = warning[API_ATTR_WARNING_COLOR]

            # Dictionary for the attribute containing the complete warning
            warning_copy = warning.copy()
            warning_copy[API_ATTR_WARNING_START] = data[f"warning_{i}_start"]
            warning_copy[API_ATTR_WARNING_END] = data[f"warning_{i}_end"]
            data[f"warning_{i}"] = warning_copy

        return data

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._api.api.data_valid

    def update(self) -> None:
        """Get the latest data from the DWD-Weather-Warnings API."""
        _LOGGER.debug(
            "Update requested for %s (%s) by %s",
            self._api.api.warncell_name,
            self._api.api.warncell_id,
            self.entity_description.key,
        )
        self._api.update()


class WrappedDwDWWAPI:
    """Wrapper for the DWD-Weather-Warnings api."""

    def __init__(self, api):
        """Initialize a DWD-Weather-Warnings wrapper."""
        self.api = api

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from the DWD-Weather-Warnings API."""
        self.api.update()
        _LOGGER.debug("Update performed")
