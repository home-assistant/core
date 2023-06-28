"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from mypermobil import (
    BATTERY_AMPERE_HOURS_LEFT,
    BATTERY_CHARGE_TIME_LEFT,
    BATTERY_CHARGING,
    BATTERY_DISTANCE_LEFT,
    BATTERY_DISTANCE_UNIT,
    BATTERY_INDOOR_DRIVE_TIME,
    BATTERY_MAX_AMPERE_HOURS,
    BATTERY_MAX_DISTANCE_LEFT,
    BATTERY_STATE_OF_CHARGE,
    BATTERY_STATE_OF_HEALTH,
    RECORDS_DISTANCE,
    RECORDS_SEATING,
    USAGE_ADJUSTMENTS,
    USAGE_DISTANCE,
    MyPermobil,
    MyPermobilAPIException,
    MyPermobilClientException,
)

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_CODE,
    CONF_EMAIL,
    CONF_REGION,
    CONF_TOKEN,
    CONF_TTL,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import APPLICATION, BATTERY_ASSUMED_VOLTAGE, DOMAIN, KM, MILES


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""


_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    if config_entry.options:
        config.update(config_entry.options)
    session = hass.helpers.aiohttp_client.async_get_clientsession()
    p_api = MyPermobil(
        application=APPLICATION,
        session=session,
        email=config.get(CONF_EMAIL),
        region=config.get(CONF_REGION),
        code=config.get(CONF_CODE),
        token=config.get(CONF_TOKEN),
        expiration_date=config.get(CONF_TTL),
    )
    p_api.self_authenticate()
    generic_sensors = [
        PermobilStateOfChargeSensor(p_api),
        PermobilStateOfHealthSensor(p_api),
        PermobilChargingSensor(p_api),
        PermobilChargeTimeLeftSensor(p_api),
        PermobilIndoorDriveTimeSensor(p_api),
        PermobilMaxWattHoursSensor(p_api),
        PermobilWattHoursLeftSensor(p_api),
        PermobilUsageAdjustmentsSensor(p_api),
        PermobilRecordAdjustmentsSensor(p_api),
    ]
    unit = await p_api.request_item(BATTERY_DISTANCE_UNIT)
    if unit not in [KM, MILES]:
        _LOGGER.error("Unknown unit of distance: %s", unit)
    ha_unit = UnitOfLength.MILES if unit == MILES else UnitOfLength.KILOMETERS
    user_specific_sensors = [
        PermobilDistanceLeftSensor(p_api, ha_unit),
        PermobilMaxDistanceLeftSensor(p_api, ha_unit),
        PermobilUsageDistanceSensor(p_api, ha_unit),
        PermobilRecordDistanceSensor(p_api, ha_unit),
    ]

    sensors = generic_sensors + user_specific_sensors
    async_add_entities(sensors, update_before_add=True)


class PermobilGenericSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_name = "Generic Sensor"

    def __init__(self, permobil: MyPermobil, item: str) -> None:
        """Initialize the sensor."""
        super().__init__()
        self._permobil = permobil
        self._item = item

    async def async_update(self) -> None:
        """Get battery percentage."""
        self._attr_native_value = await self._permobil.request_item(self._item)


class PermobilStateOfChargeSensor(PermobilGenericSensor):
    """Batter percentage sensor."""

    _attr_name = "Permobil Battery Charge"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, BATTERY_STATE_OF_CHARGE)


class PermobilStateOfHealthSensor(PermobilGenericSensor):
    """Battery health sensor."""

    _attr_name = "Permobil Battery Health"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, BATTERY_STATE_OF_HEALTH)


class PermobilChargingSensor(BinarySensorEntity):
    """Battery charging sensor."""

    _attr_name = "Permobil is Charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, permobil: MyPermobil) -> None:
        """Initialize the sensor."""
        super().__init__()
        self._permobil = permobil
        self._item = BATTERY_CHARGING

    async def async_update(self) -> None:
        """Get charging status."""
        try:
            self._attr_is_on = await self._permobil.request_item(self._item)
        except (MyPermobilClientException, MyPermobilAPIException):
            self._attr_is_on = None


class PermobilChargeTimeLeftSensor(PermobilGenericSensor):
    """Battery charge time left sensor."""

    _attr_name = "Permobil Charge Time Left"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, BATTERY_CHARGE_TIME_LEFT)


class PermobilDistanceLeftSensor(PermobilGenericSensor):
    """Battery distance left sensor."""

    _attr_name = "Permobil Distance Left"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil, unit: UnitOfLength) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, BATTERY_DISTANCE_LEFT)
        self._attr_native_unit_of_measurement = unit


class PermobilIndoorDriveTimeSensor(PermobilGenericSensor):
    """Battery indoor drive time sensor."""

    _attr_name = "Permobil Indoor Drive Time"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, BATTERY_INDOOR_DRIVE_TIME)


class PermobilMaxWattHoursSensor(PermobilGenericSensor):
    """Battery max watt hours sensor.

    converted from ampere hours by multiplying with voltage.
    """

    _attr_name = "Permobil Battery Max Watt Hours"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_value: float | None = None

    def __init__(self, permobil: MyPermobil) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, BATTERY_MAX_AMPERE_HOURS)

    async def async_update(self) -> None:
        """Get battery percentage."""
        await super().async_update()
        if self._attr_native_value:
            self._attr_native_value *= BATTERY_ASSUMED_VOLTAGE


class PermobilWattHoursLeftSensor(PermobilGenericSensor):
    """Battery ampere hours left sensor.

    converted from ampere hours by multiplying with voltage.
    """

    _attr_name = "Permobil Watt Hours Left"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_value: float | None = None

    def __init__(self, permobil: MyPermobil) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, BATTERY_AMPERE_HOURS_LEFT)

    async def async_update(self) -> None:
        """Get battery percentage."""
        await super().async_update()
        if self._attr_native_value:
            self._attr_native_value *= BATTERY_ASSUMED_VOLTAGE


class PermobilMaxDistanceLeftSensor(PermobilGenericSensor):
    """Battery max distance left sensor."""

    _attr_name = "Permobil Full Charge Distance"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil, unit: UnitOfLength) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, BATTERY_MAX_DISTANCE_LEFT)
        self._attr_native_unit_of_measurement = unit


class PermobilUsageDistanceSensor(PermobilGenericSensor):
    """usage distance sensor."""

    _attr_name = "Permobil Distance Traveled"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil, unit: UnitOfLength) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, USAGE_DISTANCE)
        self._attr_native_unit_of_measurement = unit


class PermobilUsageAdjustmentsSensor(PermobilGenericSensor):
    """usage adjustments sensor."""

    _attr_name = "Permobil Number of Adjustments"
    _attr_native_unit_of_measurement = "adjustments"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, USAGE_ADJUSTMENTS)


class PermobilRecordDistanceSensor(PermobilGenericSensor):
    """record distance sensor."""

    _attr_name = "Permobil Record Distance Traveled"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil, unit: UnitOfLength) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, RECORDS_DISTANCE)
        self._attr_native_unit_of_measurement = unit


class PermobilRecordAdjustmentsSensor(PermobilGenericSensor):
    """record adjustments sensor."""

    _attr_name = "Permobil Record Number of Adjustments"
    _attr_native_unit_of_measurement = "adjustments"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, permobil: MyPermobil) -> None:
        """Initialize the sensor."""
        super().__init__(permobil, RECORDS_SEATING)
