"""Support for getting statistical data from a DWD Weather Warnings.

Data is fetched from DWD:
https://rcccm.dwd.de/DE/wetter/warnungen_aktuell/objekt_einbindung/objekteinbindung.html

Warnungen vor extremem Unwetter (Stufe 4)
Unwetterwarnungen (Stufe 3)
Warnungen vor markantem Wetter (Stufe 2)
Wetterwarnungen (Stufe 1)
"""

from __future__ import annotations

from typing import Final

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from .const import (
    ADVANCE_WARNING_SENSOR,
    API_ATTR_WARNING_COLOR,
    API_ATTR_WARNING_DESCRIPTION,
    API_ATTR_WARNING_END,
    API_ATTR_WARNING_HEADLINE,
    API_ATTR_WARNING_INSTRUCTION,
    API_ATTR_WARNING_LEVEL,
    API_ATTR_WARNING_NAME,
    API_ATTR_WARNING_PARAMETERS,
    API_ATTR_WARNING_START,
    API_ATTR_WARNING_TYPE,
    ATTR_LAST_UPDATE,
    ATTR_REGION_ID,
    ATTR_REGION_NAME,
    ATTR_WARNING_COUNT,
    CONF_REGION_NAME,
    CURRENT_WARNING_SENSOR,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)

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

# Should be removed together with the old YAML configuration.
YAML_MONITORED_CONDITIONS: Final = [CURRENT_WARNING_SENSOR, ADVANCE_WARNING_SENSOR]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_REGION_NAME): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=YAML_MONITORED_CONDITIONS
        ): vol.All(cv.ensure_list, [vol.In(YAML_MONITORED_CONDITIONS)]),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the configurations from YAML to config flows."""
    # Show issue as long as the YAML configuration exists.
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.8.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entities from config entry."""
    api = WrappedDwDWWAPI(hass.data[DOMAIN][entry.entry_id])

    async_add_entities(
        [
            DwdWeatherWarningsSensor(api, entry.title, entry.unique_id, description)
            for description in SENSOR_TYPES
        ],
        True,
    )


class DwdWeatherWarningsSensor(SensorEntity):
    """Representation of a DWD-Weather-Warnings sensor."""

    _attr_attribution = "Data provided by DWD"

    def __init__(
        self,
        api,
        name,
        unique_id,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a DWD-Weather-Warnings sensor."""
        self._api = api
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{unique_id}-{description.key}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key == CURRENT_WARNING_SENSOR:
            return self._api.api.current_warning_level

        return self._api.api.expected_warning_level

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
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
        LOGGER.debug(
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

    @Throttle(DEFAULT_SCAN_INTERVAL)
    def update(self):
        """Get the latest data from the DWD-Weather-Warnings API."""
        self.api.update()
        LOGGER.debug("Update performed")
