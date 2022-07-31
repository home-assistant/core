"""Provides a sensor to track various status aspects of a UPS."""
from __future__ import annotations

from dataclasses import asdict
import logging
from typing import cast

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SW_VERSION,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import PyNUTData
from .const import (
    COORDINATOR,
    DOMAIN,
    KEY_STATUS,
    KEY_STATUS_DISPLAY,
    PYNUT_DATA,
    PYNUT_UNIQUE_ID,
    SENSOR_TYPES,
    STATE_TYPES,
)

NUT_DEV_INFO_TO_DEV_INFO: dict[str, str] = {
    "manufacturer": ATTR_MANUFACTURER,
    "model": ATTR_MODEL,
    "firmware": ATTR_SW_VERSION,
}

_LOGGER = logging.getLogger(__name__)


def _get_nut_device_info(data: PyNUTData) -> DeviceInfo:
    """Return a DeviceInfo object filled with NUT device info."""
    nut_dev_infos = asdict(data.device_info)
    nut_infos = {
        info_key: nut_dev_infos[nut_key]
        for nut_key, info_key in NUT_DEV_INFO_TO_DEV_INFO.items()
        if nut_dev_infos[nut_key] is not None
    }

    return cast(DeviceInfo, nut_infos)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the NUT sensors."""

    pynut_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = pynut_data[COORDINATOR]
    data = pynut_data[PYNUT_DATA]
    unique_id = pynut_data[PYNUT_UNIQUE_ID]
    status = coordinator.data

    resources = [sensor_id for sensor_id in SENSOR_TYPES if sensor_id in status]
    # Display status is a special case that falls back to the status value
    # of the UPS instead.
    if KEY_STATUS in resources:
        resources.append(KEY_STATUS_DISPLAY)

    entities = [
        NUTSensor(
            coordinator,
            SENSOR_TYPES[sensor_type],
            data,
            unique_id,
        )
        for sensor_type in resources
    ]

    async_add_entities(entities, True)


class NUTSensor(CoordinatorEntity[DataUpdateCoordinator[dict[str, str]]], SensorEntity):
    """Representation of a sensor entity for NUT status values."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, str]],
        sensor_description: SensorEntityDescription,
        data: PyNUTData,
        unique_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = sensor_description

        device_name = data.name.title()
        self._attr_name = f"{device_name} {sensor_description.name}"
        self._attr_unique_id = f"{unique_id}_{sensor_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_device_info.update(_get_nut_device_info(data))

    @property
    def native_value(self) -> str | None:
        """Return entity state from ups."""
        status = self.coordinator.data
        if self.entity_description.key == KEY_STATUS_DISPLAY:
            return _format_display_state(status)
        return status.get(self.entity_description.key)


def _format_display_state(status: dict[str, str]) -> str:
    """Return UPS display state."""
    try:
        return " ".join(STATE_TYPES[state] for state in status[KEY_STATUS].split())
    except KeyError:
        return STATE_UNKNOWN
