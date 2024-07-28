"""Sensor entities for the madVR integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MadVRConfigEntry
from .const import (
    ASPECT_DEC,
    ASPECT_INT,
    ASPECT_NAME,
    ASPECT_RES,
    INCOMING_ASPECT_RATIO,
    INCOMING_BIT_DEPTH,
    INCOMING_BLACK_LEVELS,
    INCOMING_COLOR_SPACE,
    INCOMING_COLORIMETRY,
    INCOMING_FRAME_RATE,
    INCOMING_RES,
    INCOMING_SIGNAL_TYPE,
    MASKING_DEC,
    MASKING_INT,
    MASKING_RES,
    OUTGOING_BIT_DEPTH,
    OUTGOING_BLACK_LEVELS,
    OUTGOING_COLOR_SPACE,
    OUTGOING_COLORIMETRY,
    OUTGOING_FRAME_RATE,
    OUTGOING_RES,
    OUTGOING_SIGNAL_TYPE,
    TEMP_CPU,
    TEMP_GPU,
    TEMP_HDMI,
    TEMP_MAINBOARD,
)
from .coordinator import MadVRCoordinator
from .entity import MadVREntity


def is_valid_temperature(value: float | None) -> bool:
    """Check if the temperature value is valid."""
    return value is not None and value > 0


def get_temperature(coordinator: MadVRCoordinator, key: str) -> float | None:
    """Get temperature value if valid, otherwise return None."""
    try:
        temp = float(coordinator.data.get(key, 0))
    except (AttributeError, ValueError):
        return None
    else:
        return temp if is_valid_temperature(temp) else None


@dataclass(frozen=True, kw_only=True)
class MadvrSensorEntityDescription(SensorEntityDescription):
    """Describe madVR sensor entity."""

    value_fn: Callable[[MadVRCoordinator], StateType]


SENSORS: tuple[MadvrSensorEntityDescription, ...] = (
    MadvrSensorEntityDescription(
        key=TEMP_GPU,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: get_temperature(coordinator, TEMP_GPU),
        translation_key=TEMP_GPU,
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=TEMP_HDMI,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: get_temperature(coordinator, TEMP_HDMI),
        translation_key=TEMP_HDMI,
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=TEMP_CPU,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: get_temperature(coordinator, TEMP_CPU),
        translation_key=TEMP_CPU,
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=TEMP_MAINBOARD,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: get_temperature(coordinator, TEMP_MAINBOARD),
        translation_key=TEMP_MAINBOARD,
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=INCOMING_RES,
        value_fn=lambda coordinator: coordinator.data.get(INCOMING_RES),
        translation_key=INCOMING_RES,
    ),
    MadvrSensorEntityDescription(
        key=INCOMING_SIGNAL_TYPE,
        value_fn=lambda coordinator: coordinator.data.get(INCOMING_SIGNAL_TYPE),
        translation_key=INCOMING_SIGNAL_TYPE,
        device_class=SensorDeviceClass.ENUM,
        options=["2D", "3D"],
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=INCOMING_FRAME_RATE,
        value_fn=lambda coordinator: coordinator.data.get(INCOMING_FRAME_RATE),
        translation_key=INCOMING_FRAME_RATE,
    ),
    MadvrSensorEntityDescription(
        key=INCOMING_COLOR_SPACE,
        value_fn=lambda coordinator: coordinator.data.get(INCOMING_COLOR_SPACE),
        translation_key=INCOMING_COLOR_SPACE,
        device_class=SensorDeviceClass.ENUM,
        options=["RGB", "444", "422", "420"],
    ),
    MadvrSensorEntityDescription(
        key=INCOMING_BIT_DEPTH,
        value_fn=lambda coordinator: coordinator.data.get(INCOMING_BIT_DEPTH),
        translation_key=INCOMING_BIT_DEPTH,
        device_class=SensorDeviceClass.ENUM,
        options=["8bit", "10bit", "12bit"],
    ),
    MadvrSensorEntityDescription(
        key=INCOMING_COLORIMETRY,
        value_fn=lambda coordinator: coordinator.data.get(INCOMING_COLORIMETRY),
        translation_key=INCOMING_COLORIMETRY,
        device_class=SensorDeviceClass.ENUM,
        options=["SDR", "HDR10", "HLG 601", "PAL", "709", "DCI", "2020"],
    ),
    MadvrSensorEntityDescription(
        key=INCOMING_BLACK_LEVELS,
        value_fn=lambda coordinator: coordinator.data.get(INCOMING_BLACK_LEVELS),
        translation_key=INCOMING_BLACK_LEVELS,
        device_class=SensorDeviceClass.ENUM,
        options=["TV", "PC"],
    ),
    MadvrSensorEntityDescription(
        key=INCOMING_ASPECT_RATIO,
        value_fn=lambda coordinator: coordinator.data.get(INCOMING_ASPECT_RATIO),
        translation_key=INCOMING_ASPECT_RATIO,
        device_class=SensorDeviceClass.ENUM,
        options=["16:9", "4:3"],
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=OUTGOING_RES,
        value_fn=lambda coordinator: coordinator.data.get(OUTGOING_RES),
        translation_key=OUTGOING_RES,
    ),
    MadvrSensorEntityDescription(
        key=OUTGOING_SIGNAL_TYPE,
        value_fn=lambda coordinator: coordinator.data.get(OUTGOING_SIGNAL_TYPE),
        translation_key=OUTGOING_SIGNAL_TYPE,
        device_class=SensorDeviceClass.ENUM,
        options=["2D", "3D"],
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=OUTGOING_FRAME_RATE,
        value_fn=lambda coordinator: coordinator.data.get(OUTGOING_FRAME_RATE),
        translation_key=OUTGOING_FRAME_RATE,
    ),
    MadvrSensorEntityDescription(
        key=OUTGOING_COLOR_SPACE,
        value_fn=lambda coordinator: coordinator.data.get(OUTGOING_COLOR_SPACE),
        translation_key=OUTGOING_COLOR_SPACE,
        device_class=SensorDeviceClass.ENUM,
        options=["RGB", "444", "422", "420"],
    ),
    MadvrSensorEntityDescription(
        key=OUTGOING_BIT_DEPTH,
        value_fn=lambda coordinator: coordinator.data.get(OUTGOING_BIT_DEPTH),
        translation_key=OUTGOING_BIT_DEPTH,
        device_class=SensorDeviceClass.ENUM,
        options=["8bit", "10bit", "12bit"],
    ),
    MadvrSensorEntityDescription(
        key=OUTGOING_COLORIMETRY,
        value_fn=lambda coordinator: coordinator.data.get(OUTGOING_COLORIMETRY),
        translation_key=OUTGOING_COLORIMETRY,
        device_class=SensorDeviceClass.ENUM,
        options=["SDR", "HDR10", "HLG 601", "PAL", "709", "DCI", "2020"],
    ),
    MadvrSensorEntityDescription(
        key=OUTGOING_BLACK_LEVELS,
        value_fn=lambda coordinator: coordinator.data.get(OUTGOING_BLACK_LEVELS),
        translation_key=OUTGOING_BLACK_LEVELS,
        device_class=SensorDeviceClass.ENUM,
        options=["TV", "PC"],
    ),
    MadvrSensorEntityDescription(
        key=ASPECT_RES,
        value_fn=lambda coordinator: coordinator.data.get(ASPECT_RES),
        translation_key=ASPECT_RES,
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=ASPECT_DEC,
        value_fn=lambda coordinator: coordinator.data.get(ASPECT_DEC),
        translation_key=ASPECT_DEC,
    ),
    MadvrSensorEntityDescription(
        key=ASPECT_INT,
        value_fn=lambda coordinator: coordinator.data.get(ASPECT_INT),
        translation_key=ASPECT_INT,
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=ASPECT_NAME,
        value_fn=lambda coordinator: coordinator.data.get(ASPECT_NAME),
        translation_key=ASPECT_NAME,
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=MASKING_RES,
        value_fn=lambda coordinator: coordinator.data.get(MASKING_RES),
        translation_key=MASKING_RES,
        entity_registry_enabled_default=False,
    ),
    MadvrSensorEntityDescription(
        key=MASKING_DEC,
        value_fn=lambda coordinator: coordinator.data.get(MASKING_DEC),
        translation_key=MASKING_DEC,
    ),
    MadvrSensorEntityDescription(
        key=MASKING_INT,
        value_fn=lambda coordinator: coordinator.data.get(MASKING_INT),
        translation_key=MASKING_INT,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MadVRConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(MadvrSensor(coordinator, description) for description in SENSORS)


class MadvrSensor(MadVREntity, SensorEntity):
    """Base class for madVR sensors."""

    def __init__(
        self,
        coordinator: MadVRCoordinator,
        description: MadvrSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description: MadvrSensorEntityDescription = description
        self._attr_unique_id = f"{coordinator.mac}_{description.key}"

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator)
