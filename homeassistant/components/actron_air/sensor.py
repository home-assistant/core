"""Sensor platform for Actron Air integration."""

from actron_neo_api import ActronAirPeripheral

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ActronAirConfigEntry, ActronAirSystemCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActronAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air sensor platform entities."""
    system_coordinators = entry.runtime_data.system_coordinators
    entities: list[SensorEntity] = []

    for coordinator in system_coordinators.values():
        status = coordinator.data

        # Add AC system sensors
        entities.append(AirconCleanFilterSensor(coordinator))
        entities.append(AirconDefrostModeSensor(coordinator))
        entities.append(AirconCompressorChasingTemperatureSensor(coordinator))
        entities.append(AirconCompressorLiveTemperatureSensor(coordinator))
        entities.append(AirconCompressorModeSensor(coordinator))
        entities.append(AirconCompressorSpeedSensor(coordinator))
        entities.append(AirconCompressorPowerSensor(coordinator))
        entities.append(AirconOutdoorTemperatureSensor(coordinator))

        # Add peripheral sensors
        for peripheral in status.peripherals:
            entities.append(PeripheralBatterySensor(coordinator, peripheral))
            entities.append(PeripheralHumiditySensor(coordinator, peripheral))
            entities.append(PeripheralTemperatureSensor(coordinator, peripheral))

        # Register all sensors
        async_add_entities(entities)


class BaseAirconSensor(CoordinatorEntity[ActronAirSystemCoordinator], SensorEntity):
    """Base class for Actron Air sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._status = self.coordinator.data
        self._serial_number = coordinator.serial_number

        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=self._status.ac_system.system_name,
            manufacturer="Actron Air",
            model_id=self._status.ac_system.master_wc_model,
            sw_version=self._status.ac_system.master_wc_firmware_version,
            serial_number=self._serial_number,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return not self.coordinator.is_device_stale()


class AirconCleanFilterSensor(BaseAirconSensor):
    """Representation of an Actron Air clean filter sensor."""

    _attr_translation_key = "clean_filter"

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id: str = f"{self._serial_number}_clean_filter"

    @property
    def native_value(self) -> bool | None:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, "clean_filter", None)


class AirconDefrostModeSensor(BaseAirconSensor):
    """Representation of an Actron Air defrost mode sensor."""

    _attr_translation_key = "defrost_mode"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id: str = f"{self._serial_number}_defrost_mode"

    @property
    def native_value(self) -> bool | None:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, "defrost_mode", None)


class AirconCompressorChasingTemperatureSensor(BaseAirconSensor):
    """Representation of an Actron Air compressor chasing temperature sensor."""

    _attr_translation_key = "compressor_chasing_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id: str = (
            f"{self._serial_number}_compressor_chasing_temperature"
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, "compressor_chasing_temperature", None)


class AirconCompressorLiveTemperatureSensor(BaseAirconSensor):
    """Representation of an Actron Air compressor live temperature sensor."""

    _attr_translation_key = "compressor_live_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id: str = f"{self._serial_number}_compressor_live_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, "compressor_live_temperature", None)


class AirconCompressorModeSensor(BaseAirconSensor):
    """Representation of an Actron Air compressor mode sensor."""

    _attr_translation_key = "compressor_mode"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id: str = f"{self._serial_number}_compressor_mode"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, "compressor_mode", None)


class AirconCompressorSpeedSensor(BaseAirconSensor):
    """Representation of an Actron Air compressor speed sensor."""

    _attr_translation_key = "compressor_speed"
    _attr_native_unit_of_measurement = "RPM"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id: str = f"{self._serial_number}_compressor_speed"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, "compressor_speed", None)


class AirconCompressorPowerSensor(BaseAirconSensor):
    """Representation of an Actron Air compressor power sensor."""

    _attr_translation_key = "compressor_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id: str = f"{self._serial_number}_compressor_power"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, "compressor_power", None)


class AirconOutdoorTemperatureSensor(BaseAirconSensor):
    """Representation of an Actron Air outdoor temperature sensor."""

    _attr_translation_key = "outdoor_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id: str = f"{self._serial_number}_outdoor_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, "outdoor_temperature", None)


class BasePeripheralSensor(BaseAirconSensor):
    """Base class for Actron Air peripheral sensors."""

    def __init__(
        self, coordinator: ActronAirSystemCoordinator, peripheral: ActronAirPeripheral
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._ac_serial = coordinator.serial_number
        self._peripheral = peripheral
        self._serial_number = peripheral.serial_number

        suggested_area = None
        if hasattr(peripheral, "zones") and len(peripheral.zones) == 1:
            zone = peripheral.zones[0]
            if hasattr(zone, "title") and zone.title:
                suggested_area = zone.title

        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=f"{peripheral.device_type} {peripheral.logical_address}",
            model=peripheral.device_type,
            suggested_area=suggested_area,
            via_device=(DOMAIN, self._ac_serial),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return not self.coordinator.is_device_stale()


class PeripheralBatterySensor(BasePeripheralSensor):
    """Representation of an Actron Air peripheral battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: ActronAirSystemCoordinator, peripheral: ActronAirPeripheral
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, peripheral)
        self._attr_unique_id: str = f"{peripheral.serial_number}_battery"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return getattr(self._peripheral, "battery_level", None)


class PeripheralHumiditySensor(BasePeripheralSensor):
    """Representation of an Actron Air peripheral humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: ActronAirSystemCoordinator, peripheral: ActronAirPeripheral
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, peripheral)
        self._attr_unique_id: str = f"{peripheral.serial_number}_humidity"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return getattr(self._peripheral, "humidity", None)


class PeripheralTemperatureSensor(BasePeripheralSensor):
    """Representation of an Actron Air peripheral temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: ActronAirSystemCoordinator, peripheral: ActronAirPeripheral
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, peripheral)
        self._attr_unique_id: str = f"{peripheral.serial_number}_temperature"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return getattr(self._peripheral, "temperature", None)
