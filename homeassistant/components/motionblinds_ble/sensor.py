"""Sensor entities for the MotionBlinds BLE integration."""
from __future__ import annotations

import logging
from math import ceil

from motionblindsble.const import MotionConnectionType

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
    ATTR_CONNECTION_TYPE,
    ATTR_SIGNAL_STRENGTH,
    CONF_MAC_CODE,
    DOMAIN,
    ICON_CALIBRATION,
    ICON_CONNECTION_TYPE,
    MotionCalibrationType,
)
from .cover import GenericBlind, PositionCalibrationBlind

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    ATTR_BATTERY: SensorEntityDescription(
        key=ATTR_BATTERY,
        translation_key=ATTR_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
    ),
    ATTR_CONNECTION_TYPE: SensorEntityDescription(
        key=ATTR_CONNECTION_TYPE,
        translation_key=ATTR_CONNECTION_TYPE,
        icon=ICON_CONNECTION_TYPE,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[connection_type.value for connection_type in MotionConnectionType],
        has_entity_name=True,
    ),
    ATTR_CALIBRATION: SensorEntityDescription(
        key=ATTR_CALIBRATION,
        translation_key=ATTR_CALIBRATION,
        icon=ICON_CALIBRATION,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
    ),
    ATTR_SIGNAL_STRENGTH: SensorEntityDescription(
        key=ATTR_SIGNAL_STRENGTH,
        translation_key=ATTR_SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="dBm",
        has_entity_name=True,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up battery sensors based on a config entry."""

    blind: GenericBlind = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        BatterySensor(blind),
        ConnectionSensor(blind),
        SignalStrengthSensor(blind),
    ]
    if isinstance(blind, PositionCalibrationBlind):
        entities.append(CalibrationSensor(blind))
    async_add_entities(entities)


class BatterySensor(SensorEntity):
    """Representation of a battery sensor."""

    def __init__(self, blind: GenericBlind) -> None:
        """Initialize the battery sensor."""
        _LOGGER.info(
            "(%s) Setting up battery sensor entity",
            blind.config_entry.data[CONF_MAC_CODE],
        )
        self.entity_description = SENSOR_TYPES[ATTR_BATTERY]
        self._blind = blind
        self._attr_unique_id = f"{blind.unique_id}_{ATTR_BATTERY}"
        self._attr_device_info = blind.device_info
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        self._blind.async_register_battery_callback(
            self.async_update_battery_percentage
        )
        return await super().async_added_to_hass()

    @callback
    def async_update_battery_percentage(self, battery_percentage: int | None) -> None:
        """Update the battery percentage sensor value."""
        if battery_percentage is None:
            self._attr_native_value = None
            self._attr_icon = "mdi:battery-unknown"
        elif battery_percentage == 0xFF:
            self._attr_native_value = "100"
            self._attr_icon = "mdi:power-plug-outline"
        else:
            is_charging = bool(battery_percentage & 0x80)
            battery_percentage = battery_percentage & 0x7F
            battery_icon_prefix = (
                "mdi:battery-charging" if is_charging else "mdi:battery"
            )
            self._attr_native_value = (
                str(battery_percentage) if battery_percentage is not None else None
            )
            battery_percentage_multiple_ten = ceil(battery_percentage / 10) * 10
            self._attr_icon = (
                "mdi:battery"
                if battery_percentage_multiple_ten == 100 and not is_charging
                else "mdi:battery-alert-variant-outline"
                if battery_percentage <= 5 and not is_charging
                else f"{battery_icon_prefix}-{battery_percentage_multiple_ten}"
            )

            self._attr_native_value = (
                str(battery_percentage) if battery_percentage is not None else None
            )
        self.async_write_ha_state()


class ConnectionSensor(SensorEntity):
    """Representation of a connection sensor."""

    def __init__(self, blind: GenericBlind) -> None:
        """Initialize the connection sensor."""
        _LOGGER.info(
            "(%s) Setting up connection sensor entity",
            blind.config_entry.data[CONF_MAC_CODE],
        )
        self.entity_description = SENSOR_TYPES[ATTR_CONNECTION_TYPE]
        self._blind = blind
        self._attr_unique_id = f"{blind.unique_id}_{ATTR_CONNECTION_TYPE}"
        self._attr_device_info = blind.device_info
        self._attr_native_value = MotionConnectionType.DISCONNECTED.value

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        self._blind.async_register_connection_callback(self.async_update_connection)
        return await super().async_added_to_hass()

    @callback
    def async_update_connection(
        self, connection_type: MotionConnectionType | None
    ) -> None:
        """Update the connection sensor value."""
        self._attr_native_value = connection_type.value if connection_type else None
        self.async_write_ha_state()


class CalibrationSensor(SensorEntity):
    """Representation of a calibration sensor."""

    def __init__(self, blind: PositionCalibrationBlind) -> None:
        """Initialize the calibration sensor."""
        _LOGGER.info(
            "(%s) Setting up calibration sensor entity",
            blind.config_entry.data[CONF_MAC_CODE],
        )
        self.entity_description = SENSOR_TYPES[ATTR_CALIBRATION]
        self._blind = blind
        self._attr_unique_id = f"{blind.unique_id}_{ATTR_CALIBRATION}"
        self._attr_device_info = blind.device_info
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        self._blind.async_register_calibration_callback(self.async_update_calibration)
        return await super().async_added_to_hass()

    @callback
    def async_update_calibration(
        self, calibration_type: MotionCalibrationType | None
    ) -> None:
        """Update the calibration sensor value."""
        self._attr_native_value = calibration_type
        self.async_write_ha_state()


class SignalStrengthSensor(SensorEntity):
    """Representation of a signal strength sensor."""

    def __init__(self, blind: GenericBlind) -> None:
        """Initialize the calibration sensor."""
        _LOGGER.info(
            "(%s) Setting up signal strength sensor entity",
            blind.config_entry.data[CONF_MAC_CODE],
        )
        self.entity_description = SENSOR_TYPES[ATTR_SIGNAL_STRENGTH]
        self._blind = blind
        self._attr_unique_id = f"{blind.unique_id}_{ATTR_SIGNAL_STRENGTH}"
        self._attr_device_info = blind.device_info
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        self._blind.async_register_signal_strength_callback(
            self.async_update_signal_strength
        )
        self.async_update_signal_strength(self._blind.device_rssi)
        return await super().async_added_to_hass()

    @callback
    def async_update_signal_strength(self, signal_strength: int | None) -> None:
        """Update the calibration sensor value."""
        self._attr_native_value = signal_strength
        self.async_write_ha_state()
