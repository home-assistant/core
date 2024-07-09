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
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MadVRConfigEntry
from .coordinator import MadVRCoordinator
from .entity import MadVREntity


def is_valid_temperature(value: float | None) -> bool:
    """Check if the temperature value is valid."""
    return value is not None and value > 0


def get_temperature(coordinator: MadVRCoordinator, key: str) -> float | None:
    """Get temperature value if valid, otherwise return None."""
    temp = coordinator.data.get(key)
    return float(str(temp)) if is_valid_temperature(temp) else None


@dataclass(frozen=True, kw_only=True)
class MadvrSensorEntityDescription(SensorEntityDescription):
    """Describe madVR sensor entity."""

    value_fn: Callable[[MadVRCoordinator], float | str | None]


SENSORS: tuple[MadvrSensorEntityDescription, ...] = (
    MadvrSensorEntityDescription(
        key="mac_address",
        name="MAC Address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.get("mac_address"),
        translation_key="mac_address",
    ),
    MadvrSensorEntityDescription(
        key="temp_gpu",
        name="GPU Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: get_temperature(coordinator, "temp_gpu"),
        translation_key="temp_gpu",
    ),
    MadvrSensorEntityDescription(
        key="temp_hdmi",
        name="HDMI Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: get_temperature(coordinator, "temp_hdmi"),
        translation_key="temp_hdmi",
    ),
    MadvrSensorEntityDescription(
        key="temp_cpu",
        name="CPU Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: get_temperature(coordinator, "temp_cpu"),
        translation_key="temp_cpu",
    ),
    MadvrSensorEntityDescription(
        key="temp_mainboard",
        name="Mainboard Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: get_temperature(coordinator, "temp_mainboard"),
        translation_key="temp_mainboard",
    ),
    MadvrSensorEntityDescription(
        key="incoming_res",
        name="Incoming Resolution",
        value_fn=lambda coordinator: coordinator.data.get("incoming_res"),
        translation_key="incoming_res",
    ),
    MadvrSensorEntityDescription(
        key="incoming_frame_rate",
        name="Incoming Frame Rate",
        value_fn=lambda coordinator: coordinator.data.get("incoming_frame_rate"),
        translation_key="incoming_frame_rate",
    ),
    MadvrSensorEntityDescription(
        key="incoming_color_space",
        name="Incoming Color Space",
        value_fn=lambda coordinator: coordinator.data.get("incoming_color_space"),
        translation_key="incoming_color_space",
    ),
    MadvrSensorEntityDescription(
        key="incoming_bit_depth",
        name="Incoming Bit Depth",
        value_fn=lambda coordinator: coordinator.data.get("incoming_bit_depth"),
        translation_key="incoming_bit_depth",
    ),
    MadvrSensorEntityDescription(
        key="incoming_colorimetry",
        name="Incoming Colorimetry",
        value_fn=lambda coordinator: coordinator.data.get("incoming_colorimetry"),
        translation_key="incoming_colorimetry",
    ),
    MadvrSensorEntityDescription(
        key="incoming_black_levels",
        name="Incoming Black Levels",
        value_fn=lambda coordinator: coordinator.data.get("incoming_black_levels"),
        translation_key="incoming_black_levels",
    ),
    MadvrSensorEntityDescription(
        key="incoming_aspect_ratio",
        name="Incoming Aspect Ratio",
        value_fn=lambda coordinator: coordinator.data.get("incoming_aspect_ratio"),
        translation_key="incoming_aspect_ratio",
    ),
    MadvrSensorEntityDescription(
        key="outgoing_res",
        name="Outgoing Resolution",
        value_fn=lambda coordinator: coordinator.data.get("outgoing_res"),
        translation_key="outgoing_res",
    ),
    MadvrSensorEntityDescription(
        key="outgoing_frame_rate",
        name="Outgoing Frame Rate",
        value_fn=lambda coordinator: coordinator.data.get("outgoing_frame_rate"),
        translation_key="outgoing_frame_rate",
    ),
    MadvrSensorEntityDescription(
        key="outgoing_color_space",
        name="Outgoing Color Space",
        value_fn=lambda coordinator: coordinator.data.get("outgoing_color_space"),
        translation_key="outgoing_color_space",
    ),
    MadvrSensorEntityDescription(
        key="outgoing_bit_depth",
        name="Outgoing Bit Depth",
        value_fn=lambda coordinator: coordinator.data.get("outgoing_bit_depth"),
        translation_key="outgoing_bit_depth",
    ),
    MadvrSensorEntityDescription(
        key="outgoing_colorimetry",
        name="Outgoing Colorimetry",
        value_fn=lambda coordinator: coordinator.data.get("outgoing_colorimetry"),
        translation_key="outgoing_colorimetry",
    ),
    MadvrSensorEntityDescription(
        key="outgoing_black_levels",
        name="Outgoing Black Levels",
        value_fn=lambda coordinator: coordinator.data.get("outgoing_black_levels"),
        translation_key="outgoing_black_levels",
    ),
    MadvrSensorEntityDescription(
        key="aspect_res",
        name="Aspect Ratio Resolution",
        value_fn=lambda coordinator: coordinator.data.get("aspect_res"),
        translation_key="aspect_res",
    ),
    MadvrSensorEntityDescription(
        key="aspect_dec",
        name="Aspect Ratio Decimal",
        value_fn=lambda coordinator: coordinator.data.get("aspect_dec"),
        translation_key="aspect_dec",
    ),
    MadvrSensorEntityDescription(
        key="aspect_int",
        name="Aspect Ratio Integer",
        value_fn=lambda coordinator: coordinator.data.get("aspect_int"),
        translation_key="aspect_int",
    ),
    MadvrSensorEntityDescription(
        key="aspect_name",
        name="Aspect Ratio Name",
        value_fn=lambda coordinator: coordinator.data.get("aspect_name"),
        translation_key="aspect_name",
    ),
    MadvrSensorEntityDescription(
        key="masking_res",
        name="Masking Resolution",
        value_fn=lambda coordinator: coordinator.data.get("masking_res"),
        translation_key="masking_res",
    ),
    MadvrSensorEntityDescription(
        key="masking_dec",
        name="Masking Decimal",
        value_fn=lambda coordinator: coordinator.data.get("masking_dec"),
        translation_key="masking_dec",
    ),
    MadvrSensorEntityDescription(
        key="masking_int",
        name="Masking Integer",
        value_fn=lambda coordinator: coordinator.data.get("masking_int"),
        translation_key="masking_int",
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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.native_value is not None
