"""
Platform for GPS sensor integration.
Reads sensor, position, and elevation data from PajGpsCoordinator.
"""
from __future__ import annotations
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import SENSOR_MODEL_FIELDS
from .coordinator import PajGpsCoordinator
from .__init__ import PajGpsConfigEntry
_LOGGER = logging.getLogger(__name__)
class PajGPSVoltageSensor(CoordinatorEntity[PajGpsCoordinator], SensorEntity):
    """Voltage sensor reading from coordinator sensor_data."""
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "V"
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:flash"
    _attr_name = "Voltage"

    def __init__(self, pajgps_coordinator: PajGpsCoordinator, device_id: int) -> None:
        super().__init__(pajgps_coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"pajgps_{pajgps_coordinator.entry_data['guid']}_{device_id}_voltage"

    @property
    def device_info(self) -> DeviceInfo | None:
        return self.coordinator.get_device_info(self._device_id)

    @property
    def native_value(self) -> float | None:
        sd = self.coordinator.data.sensor_data.get(self._device_id)
        if sd is None or sd.volt is None:
            return None
        value = float(sd.volt / 1000.0)  # API gives millivolts, convert to volts
        return max(0.0, min(300.0, value))

class PajGPSBatterySensor(CoordinatorEntity[PajGpsCoordinator], SensorEntity):
    """Battery level sensor reading from coordinator positions."""
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_name = "Battery Level"
    def __init__(self, pajgps_coordinator: PajGpsCoordinator, device_id: int) -> None:
        super().__init__(pajgps_coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"pajgps_{pajgps_coordinator.entry_data['guid']}_{device_id}_battery"

    @property
    def device_info(self) -> DeviceInfo | None:
        return self.coordinator.get_device_info(self._device_id)

    @property
    def native_value(self) -> int | None:
        tp = self.coordinator.data.positions.get(self._device_id)
        if tp is None or tp.battery is None:
            return None
        return max(0, min(100, int(tp.battery)))

    @property
    def icon(self) -> str:
        level = self.native_value
        if level is None:
            return "mdi:battery-alert"
        if level == 100:
            return "mdi:battery"
        if level >= 90:
            return "mdi:battery-90"
        if level >= 80:
            return "mdi:battery-80"
        if level >= 70:
            return "mdi:battery-70"
        if level >= 60:
            return "mdi:battery-60"
        if level >= 50:
            return "mdi:battery-50"
        if level >= 40:
            return "mdi:battery-40"
        if level >= 30:
            return "mdi:battery-30"
        if level >= 20:
            return "mdi:battery-20"
        if level >= 10:
            return "mdi:battery-10"
        return "mdi:battery-alert"

class PajGPSSpeedSensor(CoordinatorEntity[PajGpsCoordinator], SensorEntity):
    """Speed sensor reading from coordinator positions."""
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "km/h"
    _attr_icon = "mdi:speedometer"
    _attr_name = "Speed"
    def __init__(self, pajgps_coordinator: PajGpsCoordinator, device_id: int) -> None:
        super().__init__(pajgps_coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"pajgps_{pajgps_coordinator.entry_data['guid']}_{device_id}_speed"

    @property
    def device_info(self) -> DeviceInfo | None:
        return self.coordinator.get_device_info(self._device_id)

    @property
    def native_value(self) -> float | None:
        tp = self.coordinator.data.positions.get(self._device_id)
        if tp is None or tp.speed is None:
            return None
        return max(0.0, min(1000.0, float(tp.speed)))

class PajGPSElevationSensor(CoordinatorEntity[PajGpsCoordinator], SensorEntity):
    """Elevation sensor reading from coordinator elevations."""
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "m"
    _attr_icon = "mdi:map-marker-up"
    _attr_suggested_display_precision = 1
    _attr_name = "Elevation"
    def __init__(self, pajgps_coordinator: PajGpsCoordinator, device_id: int) -> None:
        super().__init__(pajgps_coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"pajgps_{pajgps_coordinator.entry_data['guid']}_{device_id}_elevation"

    @property
    def device_info(self) -> DeviceInfo | None:
        return self.coordinator.get_device_info(self._device_id)

    @property
    def native_value(self) -> float | None:
        elevation = self.coordinator.data.elevations.get(self._device_id)
        if elevation is None:
            return None
        return max(0.0, min(10000.0, float(elevation)))

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PajGpsConfigEntry,
    async_add_entities,
) -> None:
    """Set up PAJ GPS sensor entities from a config entry."""
    coordinator: PajGpsCoordinator = config_entry.runtime_data
    fetch_elevation = config_entry.data.get("fetch_elevation", False)
    force_battery = config_entry.data.get("force_battery", False)
    entities = []
    for device in coordinator.data.devices:
        if device.id is None:
            continue
        model = device.device_models[0] if device.device_models else {}

        entities.append(PajGPSSpeedSensor(coordinator, device.id))

        # Voltage: only if device model has a voltage sensor (alarm_volt == 1 in device_models)
        if model.get(SENSOR_MODEL_FIELDS["voltage"]):
            entities.append(PajGPSVoltageSensor(coordinator, device.id))

        # Battery: device_models.standalone_battery > 0 means a real battery is present.
        # The user can also force-add it regardless (force_battery config option).
        has_battery = model.get(SENSOR_MODEL_FIELDS["battery"], 0) > 0
        if has_battery or force_battery:
            entities.append(PajGPSBatterySensor(coordinator, device.id))

        if fetch_elevation:
            entities.append(PajGPSElevationSensor(coordinator, device.id))
    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.warning("No PAJ GPS sensor entities to add")
