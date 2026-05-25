"""Support for Qingping IoT sensors."""

from datetime import timedelta
import logging
import math

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONCENTRATION,
    CONF_ETVOC_UNIT,
    DB,
    DEVICE_MODELS,
    DOMAIN,
    ETVOC_UNIT_DISPLAY_MAP,
    INDEX,
    PERCENTAGE,
    PPM,
    SENSOR_BATTERY,
    SENSOR_CO2,
    SENSOR_ETVOC,
    SENSOR_HUMIDITY,
    SENSOR_LIGHT,
    SENSOR_NOISE,
    SENSOR_PM10,
    SENSOR_PM25,
    SENSOR_PRESSURE,
    SENSOR_SIGNAL_STRENGTH,
    SENSOR_TEMPERATURE,
    TLV_MODELS,
    Capability,
)
from .coordinator import QingpingCoordinator

_LOGGER = logging.getLogger(__name__)


# Capability -> Sensor description mapping
CAPABILITY_SENSOR_MAP: dict[Capability, dict] = {
    Capability.TEMPERATURE: {
        "sensor_type": SENSOR_TEMPERATURE,
        "translation_key": "temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    Capability.HUMIDITY: {
        "sensor_type": SENSOR_HUMIDITY,
        "translation_key": "humidity",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    Capability.CO2: {
        "sensor_type": SENSOR_CO2,
        "translation_key": "co2",
        "unit": PPM,
        "device_class": SensorDeviceClass.CO2,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    Capability.PM25: {
        "sensor_type": SENSOR_PM25,
        "translation_key": "pm25",
        "unit": CONCENTRATION,
        "device_class": SensorDeviceClass.PM25,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    Capability.PM10: {
        "sensor_type": SENSOR_PM10,
        "translation_key": "pm10",
        "unit": CONCENTRATION,
        "device_class": SensorDeviceClass.PM10,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    Capability.ETVOC: {
        "sensor_type": SENSOR_ETVOC,
        "translation_key": "etvoc",
        "unit": INDEX,
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    Capability.NOISE: {
        "sensor_type": SENSOR_NOISE,
        "translation_key": "noise",
        "unit": DB,
        "device_class": SensorDeviceClass.SOUND_PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    Capability.PRESSURE: {
        "sensor_type": SENSOR_PRESSURE,
        "translation_key": "pressure",
        "unit": "kPa",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    Capability.LIGHT: {
        "sensor_type": SENSOR_LIGHT,
        "translation_key": "light",
        "unit": "lx",
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    Capability.BATTERY: {
        "sensor_type": SENSOR_BATTERY,
        "translation_key": "battery",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    Capability.SIGNAL_STRENGTH: {
        "sensor_type": SENSOR_SIGNAL_STRENGTH,
        "translation_key": "signal_strength",
        "unit": "dBm",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "tlv_only": True,
    },
}


# Setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qingping sensors from a config entry."""
    coordinator: QingpingCoordinator = config_entry.runtime_data.coordinator

    mac = coordinator.mac
    name = coordinator.name
    model = coordinator.model

    model_info = DEVICE_MODELS[model]
    capabilities = model_info["capabilities"]

    device_info = {
        "identifiers": {(DOMAIN, mac)},
        "name": name,
        "manufacturer": "Qingping",
        "model": model,
    }

    sensors: list[SensorEntity] = []

    # Diagnostic sensors
    status_sensor = QingpingStatusSensor(coordinator, device_info)
    firmware_sensor = QingpingFirmwareSensor(coordinator, device_info)
    mac_sensor = QingpingMACSensor(coordinator, device_info)
    battery_state_sensor = QingpingBatteryStateSensor(coordinator, device_info)

    sensors.append(status_sensor)
    sensors.append(firmware_sensor)
    sensors.append(mac_sensor)

    if Capability.BATTERY in capabilities:
        sensors.append(battery_state_sensor)

    # Sensor entities based on capabilities
    is_tlv = model in TLV_MODELS
    for cap in capabilities:
        if cap not in CAPABILITY_SENSOR_MAP:
            continue
        desc = CAPABILITY_SENSOR_MAP[cap]

        if desc.get("tlv_only") and not is_tlv:
            continue

        unit = desc.get("unit")
        entity_category = desc.get("entity_category")

        sensor = QingpingSensor(
            coordinator=coordinator,
            sensor_type=desc["sensor_type"],
            translation_key=desc["translation_key"],
            unit=unit,
            device_class=desc["device_class"],
            state_class=desc["state_class"],
            device_info=device_info,
            entity_category=entity_category,
        )
        sensors.append(sensor)

    async_add_entities(sensors)

    # Periodic online status check
    async def check_status(*_):
        coordinator.check_online_status()

    config_entry.async_on_unload(
        async_track_time_interval(hass, check_status, timedelta(seconds=60))
    )


# -- Diagnostic Sensors --


class QingpingStatusSensor(CoordinatorEntity, SensorEntity):
    """Device online/offline status."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: QingpingCoordinator, device_info: dict) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_status"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str:
        """Return the online status."""
        return "online" if self.coordinator.is_online else "offline"


class QingpingFirmwareSensor(CoordinatorEntity, SensorEntity):
    """Device firmware version."""

    _attr_has_entity_name = True
    _attr_translation_key = "firmware"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: QingpingCoordinator, device_info: dict) -> None:
        """Initialize the firmware sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_firmware"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        return self.coordinator.data.get("firmware_version")


class QingpingMACSensor(CoordinatorEntity, SensorEntity):
    """Device MAC address."""

    _attr_has_entity_name = True
    _attr_translation_key = "mac"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: QingpingCoordinator, device_info: dict) -> None:
        """Initialize the MAC sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_mac"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str | None:
        """Return the MAC address."""
        return self.coordinator.data.get("mac")


class QingpingBatteryStateSensor(CoordinatorEntity, SensorEntity):
    """Battery charging state."""

    _attr_has_entity_name = True
    _attr_translation_key = "battery_state"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: QingpingCoordinator, device_info: dict) -> None:
        """Initialize the battery state sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_battery_state"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str:
        """Return the battery charging state."""
        charging = self.coordinator.data.get("battery_charging")
        if charging == "full":
            return "full"
        if charging is True:
            return "charging"
        if charging is False:
            return "discharging"
        return "unknown"


# -- Main Sensor Entity --


def _get_eTvoc_device_class(unit: str | None) -> SensorDeviceClass:
    """Get appropriate device class for VOC sensor based on unit."""
    if unit == "index":
        return None
    if unit in ("ppb", "ppm"):
        return SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
    if unit == "mg_m3":
        return SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
    return SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS


class QingpingSensor(CoordinatorEntity, SensorEntity):
    """Generic Qingping sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QingpingCoordinator,
        sensor_type: str,
        translation_key: str,
        unit: str | None,
        device_class: SensorDeviceClass,
        state_class: SensorStateClass,
        device_info: dict,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._is_unavailable = False

        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.mac}_{sensor_type}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_device_info = device_info
        if entity_category:
            self._attr_entity_category = entity_category

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data

        # Try TLV data first
        sensor_data = data.get("sensor_data")
        if isinstance(sensor_data, dict):
            self._update_from_tlv_data(sensor_data, data.get("decoded", {}))

        # Try JSON sensor data list
        for entry in data.get("sensor_data_list", []):
            self._update_from_json_data(entry)

    def _update_from_tlv_data(self, data: dict, top_level: dict) -> None:
        """Update sensor from TLV decoded data."""
        value = None

        if self._sensor_type == SENSOR_BATTERY:
            raw = top_level.get("battery") or data.get("battery")
            if raw is not None and raw >= 255:
                self._is_unavailable = True
                self._attr_native_value = None
                self.async_write_ha_state()
                return
            value = raw
        elif self._sensor_type == SENSOR_SIGNAL_STRENGTH:
            value = top_level.get("signalStrength")
            if value is not None and value >= 128:
                value -= 256
            elif value is None:
                value = data.get("rssi")
        elif self._sensor_type == SENSOR_ETVOC:
            value = data.get("tvoc")
        else:
            value = data.get(self._sensor_type)

        if value is not None:
            self._set_value(value)

    def _update_from_json_data(self, data: dict) -> None:
        """Update sensor from JSON sensorData."""
        if self._sensor_type not in data:
            return

        raw = data[self._sensor_type]
        if isinstance(raw, dict):
            value = raw.get("value")
            if self._sensor_type in (SENSOR_PM10, SENSOR_PM25) and value == 99999:
                self._is_unavailable = True
                self._attr_native_value = None
                self.async_write_ha_state()
                return
        else:
            value = raw

        if (
            self._sensor_type == SENSOR_BATTERY
            and isinstance(value, int)
            and value >= 255
        ):
            self._is_unavailable = True
            self._attr_native_value = None
            self.async_write_ha_state()
            return

        if value is not None:
            self._set_value(value)

    def _set_value(self, value: float) -> None:
        """Convert and set sensor value."""
        try:
            if self._sensor_type in {SENSOR_TEMPERATURE, SENSOR_HUMIDITY}:
                self._attr_native_value = round(float(value), 1)
            elif self._sensor_type == SENSOR_PRESSURE:
                self._attr_native_value = round(float(value), 2)
            elif self._sensor_type in (SENSOR_ETVOC):
                self._update_eTVOC_value(int(value))
            else:
                self._attr_native_value = int(value)

            self._is_unavailable = False
            self.async_write_ha_state()
        except ValueError:
            _LOGGER.error("Invalid value for %s: %s", self._sensor_type, value)

    def _update_eTVOC_value(self, raw_value: int) -> None:
        """Update eTVOC with unit conversion."""
        voc_unit = self.coordinator.data.get(CONF_ETVOC_UNIT, "index")

        if voc_unit == "ppb":
            voc_value = (math.log(501 - raw_value) - 6.24) * -2215.4
            voc_value = int(round(float(voc_value), 0))
        elif voc_unit == "mg_m3":
            voc_value = (math.log(501 - raw_value) - 6.24) * -2215.4
            voc_value = (voc_value * 4.5 * 10 + 5) / 10 / 1000
            voc_value = round(voc_value, 3)
        else:
            voc_value = raw_value

        self._attr_native_value = voc_value
        self._attr_native_unit_of_measurement = ETVOC_UNIT_DISPLAY_MAP.get(
            voc_unit, voc_unit
        )
        self._attr_device_class = _get_eTvoc_device_class(voc_unit)

    @property
    def icon(self) -> str | None:
        """Return the icon for this sensor."""
        if self._sensor_type == SENSOR_BATTERY:
            charging = self.coordinator.data.get("battery_charging")
            if charging or self._attr_native_value is None:
                return "mdi:battery-charging"
            if self._attr_native_value is not None:
                level = int(self._attr_native_value)
                bucket = max(10, (level // 10) * 10) if level > 0 else 10
                if bucket >= 100:
                    return "mdi:battery"
                return f"mdi:battery-{bucket}"
        return super().icon

    @property
    def available(self) -> bool:
        """Return True if the sensor is available."""
        if not self.coordinator.is_online:
            return False
        if self._sensor_type in (SENSOR_PM10, SENSOR_PM25):
            return not self._is_unavailable
        if self._sensor_type == SENSOR_BATTERY and self._is_unavailable:
            return False
        return True
