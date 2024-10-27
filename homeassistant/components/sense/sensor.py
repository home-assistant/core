"""Support for monitoring a Sense energy sensor."""

from datetime import datetime

from sense_energy import ASyncSenseable, Scale
from sense_energy.sense_api import SenseDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SenseConfigEntry
from .const import (
    ACTIVE_NAME,
    ACTIVE_TYPE,
    ATTRIBUTION,
    CONSUMPTION_ID,
    CONSUMPTION_NAME,
    DOMAIN,
    FROM_GRID_ID,
    FROM_GRID_NAME,
    MDI_ICONS,
    NET_PRODUCTION_ID,
    NET_PRODUCTION_NAME,
    PRODUCTION_ID,
    PRODUCTION_NAME,
    PRODUCTION_PCT_ID,
    PRODUCTION_PCT_NAME,
    SOLAR_POWERED_ID,
    SOLAR_POWERED_NAME,
    TO_GRID_ID,
    TO_GRID_NAME,
)
from .coordinator import (
    SenseCoordinator,
    SenseRealtimeCoordinator,
    SenseTrendCoordinator,
)

# Sensor types/ranges
TRENDS_SENSOR_TYPES = {
    Scale.DAY: "Daily",
    Scale.WEEK: "Weekly",
    Scale.MONTH: "Monthly",
    Scale.YEAR: "Yearly",
    Scale.CYCLE: "Bill",
}

# Production/consumption variants
SENSOR_VARIANTS = [(PRODUCTION_ID, PRODUCTION_NAME), (CONSUMPTION_ID, CONSUMPTION_NAME)]

# Trend production/consumption variants
TREND_SENSOR_VARIANTS = [
    *SENSOR_VARIANTS,
    (PRODUCTION_PCT_ID, PRODUCTION_PCT_NAME),
    (NET_PRODUCTION_ID, NET_PRODUCTION_NAME),
    (FROM_GRID_ID, FROM_GRID_NAME),
    (TO_GRID_ID, TO_GRID_NAME),
    (SOLAR_POWERED_ID, SOLAR_POWERED_NAME),
]


def sense_to_mdi(sense_icon: str) -> str:
    """Convert sense icon to mdi icon."""
    return f"mdi:{MDI_ICONS.get(sense_icon, 'power-plug')}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SenseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sense sensor."""
    data = config_entry.runtime_data.data
    trends_coordinator = config_entry.runtime_data.trends
    realtime_coordinator = config_entry.runtime_data.rt

    # Request only in case it takes longer
    # than 60s
    await trends_coordinator.async_request_refresh()

    sense_monitor_id = data.sense_monitor_id

    entities: list[SensorEntity] = [
        SenseDevicePowerSensor(device, sense_monitor_id, realtime_coordinator)
        for device in config_entry.runtime_data.data.devices
    ]

    for variant_id, variant_name in SENSOR_VARIANTS:
        entities.append(
            SensePowerSensor(
                data, sense_monitor_id, variant_id, variant_name, realtime_coordinator
            )
        )

    entities.extend(
        SenseVoltageSensor(data, i, sense_monitor_id, realtime_coordinator)
        for i in range(len(data.active_voltage))
    )

    for scale in Scale:
        for variant_id, variant_name in TREND_SENSOR_VARIANTS:
            entities.append(
                SenseTrendsSensor(
                    data,
                    scale,
                    variant_id,
                    variant_name,
                    trends_coordinator,
                    sense_monitor_id,
                )
            )

    async_add_entities(entities)


class SenseBaseSensor(CoordinatorEntity[SenseCoordinator], SensorEntity):
    """Base implementation of a Sense sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SenseCoordinator,
        sense_monitor_id: str,
        unique_id: str,
    ) -> None:
        """Initialize the Sense sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{sense_monitor_id}-{unique_id}"


class SensePowerSensor(SenseBaseSensor):
    """Implementation of a Sense energy sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        data: ASyncSenseable,
        sense_monitor_id: str,
        variant_id: str,
        variant_name: str,
        realtime_coordinator: SenseRealtimeCoordinator,
    ) -> None:
        """Initialize the Sense sensor."""
        super().__init__(
            realtime_coordinator, sense_monitor_id, f"{ACTIVE_TYPE}-{variant_id}"
        )
        self._attr_name = f"{ACTIVE_NAME} {variant_name}"
        self._data = data
        self._variant_id = variant_id

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return round(
            self._data.active_solar_power
            if self._variant_id == PRODUCTION_ID
            else self._data.active_power
        )


class SenseVoltageSensor(SenseBaseSensor):
    """Implementation of a Sense energy voltage sensor."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(
        self,
        data: ASyncSenseable,
        index: int,
        sense_monitor_id: str,
        realtime_coordinator: SenseRealtimeCoordinator,
    ) -> None:
        """Initialize the Sense sensor."""
        super().__init__(realtime_coordinator, sense_monitor_id, f"L{index + 1}")
        self._attr_name = f"L{index + 1} Voltage"
        self._data = data
        self._voltage_index = index

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return round(self._data.active_voltage[self._voltage_index], 1)


class SenseTrendsSensor(SenseBaseSensor):
    """Implementation of a Sense energy sensor."""

    def __init__(
        self,
        data: ASyncSenseable,
        scale: Scale,
        variant_id: str,
        variant_name: str,
        trends_coordinator: SenseTrendCoordinator,
        sense_monitor_id: str,
    ) -> None:
        """Initialize the Sense sensor."""
        super().__init__(
            trends_coordinator,
            sense_monitor_id,
            f"{TRENDS_SENSOR_TYPES[scale].lower()}-{variant_id}",
        )
        self._attr_name = f"{TRENDS_SENSOR_TYPES[scale]} {variant_name}"
        self._data = data
        self._scale = scale
        self._variant_id = variant_id
        self._had_any_update = False
        if variant_id in [PRODUCTION_PCT_ID, SOLAR_POWERED_ID]:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_entity_registry_enabled_default = False
            self._attr_state_class = None
            self._attr_device_class = None
        else:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_info = DeviceInfo(
            name=f"Sense {sense_monitor_id}",
            identifiers={(DOMAIN, sense_monitor_id)},
            model="Sense",
            manufacturer="Sense Labs, Inc.",
            configuration_url="https://home.sense.com",
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return round(self._data.get_stat(self._scale, self._variant_id), 1)

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        if self._attr_state_class == SensorStateClass.TOTAL:
            return self._data.trend_start(self._scale)
        return None


class SenseDevicePowerSensor(SenseBaseSensor):
    """Implementation of a Sense energy device."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER

    def __init__(
        self,
        device: SenseDevice,
        sense_monitor_id: str,
        realtime_coordinator: SenseRealtimeCoordinator,
    ) -> None:
        """Initialize the Sense binary sensor."""
        super().__init__(
            realtime_coordinator, sense_monitor_id, f"{device.id}-{CONSUMPTION_ID}"
        )
        self._attr_name = f"{device.name} {CONSUMPTION_NAME}"
        self._id = device.id
        self._attr_icon = sense_to_mdi(device.icon)
        self._device = device

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.power_w
