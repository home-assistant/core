"""Support for TPLink HS100/HS110/HS200 smart switch energy sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging
from typing import cast

from kasa import SmartDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_VOLTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import legacy_device_id
from .const import (
    ATTR_CURRENT_A,
    ATTR_CURRENT_POWER_W,
    ATTR_TODAY_ENERGY_KWH,
    ATTR_TOTAL_ENERGY_KWH,
    DOMAIN,
)
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity

_LOGGER = logging.getLogger(__name__)


AcceptedValueFnReturnValues = float | datetime.datetime | int | None


@dataclass
class TPLinkSensorEntityDescriptionMixin:
    """Describes TPLink sensor entity."""

    attribute_name: str
    value_fn: Callable[
        [SmartDevice, TPLinkSensorEntityDescription], AcceptedValueFnReturnValues
    ]
    precision: int | None


@dataclass
class TPLinkSensorEntityDescription(
    SensorEntityDescription, TPLinkSensorEntityDescriptionMixin
):
    """Describes TPLink sensor entity."""


def async_handle_emeter_attr(
    device: SmartDevice, description: TPLinkSensorEntityDescription
) -> float | None:
    """Map an emeter sensor key to the device attribute."""
    if not device.has_emeter:
        return None

    # special handling for today's consumption
    if description.key == ATTR_TODAY_ENERGY_KWH:
        if (emeter_today := device.emeter_today) is not None:
            return round(cast(float, emeter_today), description.precision)
        # today's consumption not available, when device was off all the day
        # bulb's do not report this information, so filter it out
        return None if device.is_bulb else 0.0

    if (val := getattr(device.emeter_realtime, description.attribute_name)) is None:
        return None

    return round(cast(float, val), description.precision)


def async_handle_timestamp(
    device: SmartDevice, description: TPLinkSensorEntityDescription
) -> datetime.datetime | None:
    """Return local timestamp.

    As the backend library does not currently provide the information about the local timezone
    in a sane manner, we consider all devices to be on the same timezone as the homeassistant instance.
    """
    if (value := getattr(device, description.attribute_name)) is not None:
        return dt_util.as_local(value)

    return None


def async_handle_int_value(
    device: SmartDevice, description: TPLinkSensorEntityDescription
) -> int | None:
    """Return value for the attribute defined in the description.

    This should be converted to use generics to pass the expected type.
    """
    if (
        description.attribute_name is not None
        and (value := getattr(device, description.attribute_name)) is not None
    ):
        return cast(int, value)

    return None


SENSORS: tuple[TPLinkSensorEntityDescription, ...] = (
    TPLinkSensorEntityDescription(
        key=ATTR_CURRENT_POWER_W,
        translation_key="current_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_name="power",
        value_fn=async_handle_emeter_attr,
        precision=1,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_KWH,
        translation_key="total_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        attribute_name="total",
        value_fn=async_handle_emeter_attr,
        precision=3,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_TODAY_ENERGY_KWH,
        translation_key="today_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        attribute_name="emeter_today",
        precision=3,
        value_fn=async_handle_emeter_attr,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_name="voltage",
        value_fn=async_handle_emeter_attr,
        precision=1,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_CURRENT_A,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_name="current",
        value_fn=async_handle_emeter_attr,
        precision=2,
    ),
    TPLinkSensorEntityDescription(
        key="on_since",
        name="On Since",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        attribute_name="on_since",
        value_fn=async_handle_timestamp,
        precision=None,
    ),
    TPLinkSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        attribute_name="rssi",
        value_fn=async_handle_int_value,
        precision=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: TPLinkDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[SmartPlugSensor] = []
    parent = coordinator.device

    def _async_sensors_for_device(device: SmartDevice) -> list[SmartPlugSensor]:
        sensors = [
            SmartPlugSensor(device, coordinator, description)
            for description in SENSORS
            if description.value_fn(device, description) is not None
        ]
        return sensors

    if parent.is_strip:
        # Historically we only add the children if the device is a strip
        for child in parent.children:
            entities.extend(_async_sensors_for_device(child))
    else:
        entities.extend(_async_sensors_for_device(parent))

    async_add_entities(entities)


class SmartPlugSensor(CoordinatedTPLinkEntity, SensorEntity):
    """Representation of a TPLink Smart Plug energy sensor."""

    entity_description: TPLinkSensorEntityDescription

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        description: TPLinkSensorEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{legacy_device_id(self.device)}_{self.entity_description.key}"
        )
        self.timezone = self.coordinator.hass.config.time_zone

    @property
    def native_value(self) -> float | datetime.datetime | None:
        """Return the sensors state."""
        return self.entity_description.value_fn(self.device, self.entity_description)
