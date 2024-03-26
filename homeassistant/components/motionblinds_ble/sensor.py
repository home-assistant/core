"""Sensor entities for the Motionblinds BLE integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from math import ceil

from motionblindsble.const import (
    MotionBlindType,
    MotionCalibrationType,
    MotionConnectionType,
)
from motionblindsble.device import MotionDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BATTERY,
    ATTR_CALIBRATION,
    ATTR_CONNECTION,
    ATTR_SIGNAL_STRENGTH,
    CONF_MAC_CODE,
    DOMAIN,
)
from .entity import MotionblindsBLEEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MotionblindsBLESensorEntityDescription(SensorEntityDescription):
    """Entity description of a sensor entity with initial_value attribute."""

    initial_value: str | None = None


SENSOR_TYPES: dict[str, MotionblindsBLESensorEntityDescription] = {
    ATTR_BATTERY: MotionblindsBLESensorEntityDescription(
        key=ATTR_BATTERY,
        translation_key=ATTR_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_CONNECTION: MotionblindsBLESensorEntityDescription(
        key=ATTR_CONNECTION,
        translation_key=ATTR_CONNECTION,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[connection_type.value for connection_type in MotionConnectionType],
        initial_value=MotionConnectionType.DISCONNECTED.value,
    ),
    ATTR_CALIBRATION: MotionblindsBLESensorEntityDescription(
        key=ATTR_CALIBRATION,
        translation_key=ATTR_CALIBRATION,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_SIGNAL_STRENGTH: MotionblindsBLESensorEntityDescription(
        key=ATTR_SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="dBm",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entities based on a config entry."""

    device: MotionDevice = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        BatterySensor(device, entry, SENSOR_TYPES[ATTR_BATTERY]),
        ConnectionSensor(device, entry, SENSOR_TYPES[ATTR_CONNECTION]),
        SignalStrengthSensor(device, entry, SENSOR_TYPES[ATTR_SIGNAL_STRENGTH]),
    ]
    if device.blind_type in {MotionBlindType.CURTAIN, MotionBlindType.VERTICAL}:
        entities.append(
            CalibrationSensor(device, entry, SENSOR_TYPES[ATTR_CALIBRATION])
        )

    async_add_entities(entities)


class MotionblindsBLESensorEntity(MotionblindsBLEEntity, SensorEntity):
    """Representation of a sensor entity."""

    def __init__(
        self,
        device: MotionDevice,
        entry: ConfigEntry,
        entity_description: MotionblindsBLESensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(
            device, entry, entity_description, unique_id_suffix=entity_description.key
        )
        self._attr_native_value = entity_description.initial_value

    async def async_added_to_hass(self) -> None:
        """Log sensor entity information."""
        _LOGGER.debug(
            "(%s) Setting up %s sensor entity",
            self.entry.data[CONF_MAC_CODE],
            self.entity_description.key.replace("_", " "),
        )


class BatterySensor(MotionblindsBLESensorEntity):
    """Representation of a battery sensor entity."""

    async def async_added_to_hass(self) -> None:
        """Register device callbacks."""
        await super().async_added_to_hass()
        self.device.register_battery_callback(self.async_update_battery)

    @callback
    def async_update_battery(
        self,
        battery_percentage: int | None,
        is_charging: bool | None,
        is_wired: bool | None,
    ) -> None:
        """Update the battery sensor value and icon."""
        self._attr_native_value = (
            str(battery_percentage) if battery_percentage is not None else None
        )
        if battery_percentage is None:
            # Battery percentage is unknown
            self._attr_icon = "mdi:battery-unknown"
        elif is_wired:
            # Motor is wired and does not have a battery
            self._attr_icon = "mdi:power-plug-outline"
        elif battery_percentage > 90 and not is_charging:
            # Full battery icon if battery > 90% and not charging
            self._attr_icon = "mdi:battery"
        elif battery_percentage <= 5 and not is_charging:
            # Empty battery icon with alert if battery <= 5% and not charging
            self._attr_icon = "mdi:battery-alert-variant-outline"
        else:
            battery_icon_prefix = (
                "mdi:battery-charging" if is_charging else "mdi:battery"
            )
            battery_percentage_multiple_ten = ceil(battery_percentage / 10) * 10
            self._attr_icon = f"{battery_icon_prefix}-{battery_percentage_multiple_ten}"
        self.async_write_ha_state()


class ConnectionSensor(MotionblindsBLESensorEntity):
    """Representation of a connection sensor entity."""

    async def async_added_to_hass(self) -> None:
        """Register device callbacks."""
        await super().async_added_to_hass()
        self.device.register_connection_callback(self.async_update_connection)

    @callback
    def async_update_connection(
        self, connection_type: MotionConnectionType | None
    ) -> None:
        """Update the connection sensor value."""
        self._attr_native_value = connection_type.value if connection_type else None
        self.async_write_ha_state()


class CalibrationSensor(MotionblindsBLESensorEntity):
    """Representation of a calibration sensor entity."""

    async def async_added_to_hass(self) -> None:
        """Register device callbacks."""
        await super().async_added_to_hass()
        self.device.register_calibration_callback(self.async_update_calibration)

    @callback
    def async_update_calibration(
        self, calibration_type: MotionCalibrationType | None
    ) -> None:
        """Update the calibration sensor value."""
        self._attr_native_value = (
            calibration_type.value if calibration_type is not None else None
        )
        self.async_write_ha_state()


class SignalStrengthSensor(MotionblindsBLESensorEntity):
    """Representation of a signal strength sensor entity."""

    async def async_added_to_hass(self) -> None:
        """Register device callbacks and update signal strength."""
        await super().async_added_to_hass()
        self.device.register_signal_strength_callback(self.async_update_signal_strength)
        self.async_update_signal_strength(self.device.rssi)

    @callback
    def async_update_signal_strength(self, signal_strength: int | None) -> None:
        """Update the signal strength sensor value."""
        self._attr_native_value = (
            str(signal_strength) if signal_strength is not None else None
        )
        self.async_write_ha_state()
