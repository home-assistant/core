"""Support for getting statistical data from a DWD Weather Warnings.

Data is fetched from DWD:
https://rcccm.dwd.de/DE/wetter/warnungen_aktuell/objekt_einbindung/objekteinbindung.html

Warnungen vor extremem Unwetter (Stufe 4)  # codespell:ignore vor
Unwetterwarnungen (Stufe 3)
Warnungen vor markantem Wetter (Stufe 2)  # codespell:ignore vor
Wetterwarnungen (Stufe 1)
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    CURRENT_WARNING_SENSOR,
    DOMAIN,
)
from .coordinator import DwdWeatherWarningsConfigEntry, DwdWeatherWarningsCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CURRENT_WARNING_SENSOR,
        translation_key=CURRENT_WARNING_SENSOR,
    ),
    SensorEntityDescription(
        key=ADVANCE_WARNING_SENSOR,
        translation_key=ADVANCE_WARNING_SENSOR,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DwdWeatherWarningsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities from config entry."""
    coordinator = entry.runtime_data

    unique_id = entry.unique_id
    assert unique_id

    async_add_entities(
        DwdWeatherWarningsSensor(coordinator, description, unique_id)
        for description in SENSOR_TYPES
    )


class DwdWeatherWarningsSensor(
    CoordinatorEntity[DwdWeatherWarningsCoordinator], SensorEntity
):
    """Representation of a DWD-Weather-Warnings sensor."""

    _attr_attribution = "Data provided by DWD"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DwdWeatherWarningsCoordinator,
        description: SensorEntityDescription,
        unique_id: str,
    ) -> None:
        """Initialize a DWD-Weather-Warnings sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{unique_id}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=coordinator.api.warncell_name,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.entity_description.key == CURRENT_WARNING_SENSOR:
            return self.coordinator.api.current_warning_level

        return self.coordinator.api.expected_warning_level

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        data = {
            ATTR_REGION_NAME: self.coordinator.api.warncell_name,
            ATTR_REGION_ID: self.coordinator.api.warncell_id,
            ATTR_LAST_UPDATE: self.coordinator.api.last_update,
        }

        if self.entity_description.key == CURRENT_WARNING_SENSOR:
            searched_warnings = self.coordinator.api.current_warnings
        else:
            searched_warnings = self.coordinator.api.expected_warnings

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

            # Dictionary for the attribute containing the complete warning.
            warning_copy = warning.copy()
            warning_copy[API_ATTR_WARNING_START] = data[f"warning_{i}_start"]
            warning_copy[API_ATTR_WARNING_END] = data[f"warning_{i}_end"]
            data[f"warning_{i}"] = warning_copy

        return data

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self.coordinator.api.data_valid
