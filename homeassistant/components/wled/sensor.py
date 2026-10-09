"""Support for WLED sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

from wled import Device as WLEDDevice

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .coordinator import WLEDConfigEntry, WLEDDataUpdateCoordinator
from .entity import WLEDEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WLEDSensorEntityDescription(SensorEntityDescription):
    """Describes WLED sensor entity."""

    exists_fn: Callable[[WLEDDevice], bool] = lambda _: True
    unit_fn: Callable[[WLEDDevice], str | None] | None = None
    value_fn: Callable[[WLEDDevice], datetime | StateType]


# The units usermods report their readings in, as Home Assistant knows them.
_USERMOD_UNITS = {
    "°C": UnitOfTemperature.CELSIUS,
    "C": UnitOfTemperature.CELSIUS,
    "°F": UnitOfTemperature.FAHRENHEIT,
    "F": UnitOfTemperature.FAHRENHEIT,
    "RH": PERCENTAGE,
    "%RH": PERCENTAGE,
    "%": PERCENTAGE,
}


def _usermod_reading(device: WLEDDevice, reading: str) -> tuple[float, str] | None:
    """Return a usermod reading and its unit, if it's a number in a known unit."""
    if (
        device.info.sensor is None
        or (sensor := device.info.sensor.get(reading)) is None
        or sensor.unit is None
        or (unit := _USERMOD_UNITS.get(sensor.unit.replace(" ", ""))) is None
        or isinstance(sensor.value, bool)
        or not isinstance(sensor.value, (int, float))
    ):
        return None

    return sensor.value, unit


def _usermod_sensor(
    key: str, reading: str, **kwargs: Any
) -> WLEDSensorEntityDescription:
    """Describe a sensor for a reading a usermod reports, like a temperature."""
    return WLEDSensorEntityDescription(
        key=key,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda device: _usermod_reading(device, reading) is not None,
        unit_fn=lambda device: (
            measured[1] if (measured := _usermod_reading(device, reading)) else None
        ),
        value_fn=lambda device: (
            measured[0] if (measured := _usermod_reading(device, reading)) else None
        ),
        **kwargs,
    )


SENSORS: tuple[WLEDSensorEntityDescription, ...] = (
    WLEDSensorEntityDescription(
        key="estimated_current",
        translation_key="estimated_current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.leds.power,
        # The power budget is only reported for a global current limit, while
        # the estimate itself is also reported when limiting per output.
        exists_fn=lambda device: bool(device.info.leds.power),
    ),
    WLEDSensorEntityDescription(
        key="info_leds_count",
        translation_key="info_leds_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.leds.count,
    ),
    WLEDSensorEntityDescription(
        key="info_leds_max_power",
        translation_key="info_leds_max_power",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        value_fn=lambda device: device.info.leds.max_power,
        exists_fn=lambda device: bool(device.info.leds.max_power),
    ),
    WLEDSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: utcnow() - device.info.uptime,
    ),
    WLEDSensorEntityDescription(
        key="free_heap",
        translation_key="free_heap",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.free_heap,
    ),
    WLEDSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.signal if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.rssi if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_channel",
        translation_key="wifi_channel",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.channel if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_bssid",
        translation_key="wifi_bssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.bssid if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="ip",
        translation_key="ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.ip,
    ),
    # Readings of usermods, like a DS18B20 temperature sensor or an SHT
    # temperature and humidity sensor. Each is a number in a unit.
    _usermod_sensor(
        "usermod_temperature",
        "temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    _usermod_sensor(
        "usermod_sht_temperature",
        "temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    _usermod_sensor(
        "usermod_sht_humidity",
        "humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    _usermod_sensor(
        "usermod_internal_temperature",
        "Internal Temperature",
        translation_key="internal_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WLED sensor based on a config entry."""
    coordinator = entry.runtime_data
    added: set[str] = set()

    # Sensors added before stay, even when the device doesn't report what they
    # need right now, like the current while the light is off.
    registered = {
        registry_entry.unique_id
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if registry_entry.domain == SENSOR_DOMAIN
    }
    mac_address = coordinator.data.info.mac_address

    @callback
    def _async_add_sensors() -> None:
        """Add the sensors the device reports, as soon as it does.

        Some only show up later: WLED reports no current while the light is
        off, so a device that's off when set up gets those sensors once it's on.
        """
        sensors = [
            WLEDSensorEntity(coordinator, description)
            for description in SENSORS
            if description.key not in added
            and (
                description.exists_fn(coordinator.data)
                or f"{mac_address}_{description.key}" in registered
            )
        ]
        added.update(sensor.entity_description.key for sensor in sensors)
        if sensors:
            async_add_entities(sensors)

    _async_add_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_sensors))


class WLEDSensorEntity(WLEDEntity, SensorEntity):
    """Defines a WLED sensor entity."""

    entity_description: WLEDSensorEntityDescription

    def __init__(
        self,
        coordinator: WLEDDataUpdateCoordinator,
        description: WLEDSensorEntityDescription,
    ) -> None:
        """Initialize a WLED sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_{description.key}"
        self._update_unit()

    def _update_unit(self) -> None:
        """Follow the unit the device reports, like Celsius or Fahrenheit.

        While it reports none, like on a sensor error, the last one stays.
        """
        if (unit_fn := self.entity_description.unit_fn) is not None and (
            unit := unit_fn(self.coordinator.data)
        ) is not None:
            self._attr_native_unit_of_measurement = unit

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_unit()
        super()._handle_coordinator_update()

    @property
    @override
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
