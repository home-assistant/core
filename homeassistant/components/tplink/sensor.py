"""Support for TPLink HS100/HS110/HS200 smart switch energy sensors."""
from __future__ import annotations

from dataclasses import dataclass
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
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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


@dataclass
class TPLinkSensorEntityDescription(SensorEntityDescription):
    """Describes TPLink sensor entity."""

    emeter_attr: str | None = None
    precision: int | None = None


ENERGY_SENSORS: tuple[TPLinkSensorEntityDescription, ...] = (
    TPLinkSensorEntityDescription(
        key=ATTR_CURRENT_POWER_W,
        translation_key="current_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_attr="power",
        precision=1,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_KWH,
        translation_key="total_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        emeter_attr="total",
        precision=3,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_TODAY_ENERGY_KWH,
        translation_key="today_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        precision=3,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_attr="voltage",
        precision=1,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_CURRENT_A,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_attr="current",
        precision=2,
    ),
)


def async_emeter_from_device(
    device: SmartDevice, description: TPLinkSensorEntityDescription
) -> float | None:
    """Map a sensor key to the device attribute."""
    if attr := description.emeter_attr:
        if (val := getattr(device.emeter_realtime, attr)) is None:
            return None
        return round(cast(float, val), description.precision)

    # ATTR_TODAY_ENERGY_KWH
    if (emeter_today := device.emeter_today) is not None:
        return round(cast(float, emeter_today), description.precision)
    # today's consumption not available, when device was off all the day
    # bulb's do not report this information, so filter it out
    return None if device.is_bulb else 0.0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: TPLinkDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[SmartPlugSensor] = []
    parent = coordinator.device
    if not parent.has_emeter:
        return

    def _async_sensors_for_device(device: SmartDevice) -> list[SmartPlugSensor]:
        return [
            SmartPlugSensor(device, coordinator, description)
            for description in ENERGY_SENSORS
            if async_emeter_from_device(device, description) is not None
        ]

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

    @property
    def native_value(self) -> float | None:
        """Return the sensors state."""
        return async_emeter_from_device(self.device, self.entity_description)
