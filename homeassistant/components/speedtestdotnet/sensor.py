"""Support for Speedtest.net internet speed testing sensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BYTES_RECEIVED,
    ATTR_BYTES_SENT,
    ATTR_SERVER_COUNTRY,
    ATTR_SERVER_ID,
    ATTR_SERVER_NAME,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    ICON,
)
from .coordinator import SpeedTestDataCoordinator


@dataclass(frozen=True)
class SpeedtestSensorEntityDescription(SensorEntityDescription):
    """Class describing Speedtest sensor entities."""

    value: Callable = round


SENSOR_TYPES: tuple[SpeedtestSensorEntityDescription, ...] = (
    SpeedtestSensorEntityDescription(
        key="ping",
        translation_key="ping",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
    ),
    SpeedtestSensorEntityDescription(
        key="download",
        translation_key="download",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        value=lambda value: round(value / 10**6, 2),
    ),
    SpeedtestSensorEntityDescription(
        key="upload",
        translation_key="upload",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        value=lambda value: round(value / 10**6, 2),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Speedtestdotnet sensors."""
    speedtest_coordinator = hass.data[DOMAIN]
    async_add_entities(
        SpeedtestSensor(speedtest_coordinator, description)
        for description in SENSOR_TYPES
    )


class SpeedtestSensor(CoordinatorEntity[SpeedTestDataCoordinator], SensorEntity):
    """Implementation of a speedtest.net sensor."""

    entity_description: SpeedtestSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_icon = ICON

    def __init__(
        self,
        coordinator: SpeedTestDataCoordinator,
        description: SpeedtestSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = description.key
        self._state: StateType = None
        self._attrs: dict[str, Any] = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=DEFAULT_NAME,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.speedtest.net/",
        )

    @property
    def native_value(self) -> StateType:
        """Return native value for entity."""
        if self.coordinator.data:
            state = self.coordinator.data[self.entity_description.key]
            self._state = cast(StateType, self.entity_description.value(state))
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data:
            self._attrs.update(
                {
                    ATTR_SERVER_NAME: self.coordinator.data["server"]["name"],
                    ATTR_SERVER_COUNTRY: self.coordinator.data["server"]["country"],
                    ATTR_SERVER_ID: self.coordinator.data["server"]["id"],
                }
            )

            if self.entity_description.key == "download":
                self._attrs[ATTR_BYTES_RECEIVED] = self.coordinator.data[
                    ATTR_BYTES_RECEIVED
                ]
            elif self.entity_description.key == "upload":
                self._attrs[ATTR_BYTES_SENT] = self.coordinator.data[ATTR_BYTES_SENT]

        return self._attrs
