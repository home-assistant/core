"""Sensor platform for Actron Air integration."""

from actron_neo_api import ActronAirZone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
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

    # sensor_configs = [
    #     (
    #         "clean_filter",
    #         "clean_filter",
    #         SensorDeviceClass.ENUM,
    #         None,
    #         DIAGNOSTIC_CATEGORY,
    #         SensorStateClass.MEASUREMENT,
    #         True,
    #     ),
    #     (
    #         "defrost_mode",
    #         "defrost_mode",
    #         SensorDeviceClass.ENUM,
    #         None,
    #         DIAGNOSTIC_CATEGORY,
    #         SensorStateClass.MEASUREMENT,
    #         False,
    #     ),
    #     (
    #         "compressor_chasing_temperature",
    #         "compressor_chasing_temperature",
    #         SensorDeviceClass.TEMPERATURE,
    #         UnitOfTemperature.CELSIUS,
    #         DIAGNOSTIC_CATEGORY,
    #         SensorStateClass.MEASUREMENT,
    #         False,
    #     ),
    #     (
    #         "compressor_live_temperature",
    #         "compressor_live_temperature",
    #         SensorDeviceClass.TEMPERATURE,
    #         UnitOfTemperature.CELSIUS,
    #         DIAGNOSTIC_CATEGORY,
    #         SensorStateClass.MEASUREMENT,
    #         False,
    #     ),
    #     (
    #         "compressor_mode",
    #         "compressor_mode",
    #         SensorDeviceClass.ENUM,
    #         None,
    #         DIAGNOSTIC_CATEGORY,
    #         None,
    #         False,
    #     ),
    #     (
    #         "system_on",
    #         "system_on",
    #         SensorDeviceClass.ENUM,
    #         None,
    #         None,
    #         None,
    #         True,
    #     ),
    #     (
    #         "compressor_speed",
    #         "compressor_speed",
    #         SensorDeviceClass.SPEED,
    #         None,
    #         DIAGNOSTIC_CATEGORY,
    #         SensorStateClass.MEASUREMENT,
    #         False,
    #     ),
    #     (
    #         "compressor_power",
    #         "compressor_power",
    #         SensorDeviceClass.POWER,
    #         UnitOfPower.WATT,
    #         DIAGNOSTIC_CATEGORY,
    #         SensorStateClass.MEASUREMENT,
    #         False,
    #     ),
    #     (
    #         "outdoor_temperature",
    #         "outdoor_temperature",
    #         SensorDeviceClass.TEMPERATURE,
    #         UnitOfTemperature.CELSIUS,
    #         None,
    #         SensorStateClass.MEASUREMENT,
    #         True,
    #     ),
    #     (
    #         "humidity",
    #         "humidity",
    #         SensorDeviceClass.HUMIDITY,
    #         PERCENTAGE,
    #         None,
    #         SensorStateClass.MEASUREMENT,
    #         True,
    #     ),
    # ]

    for coordinator in system_coordinators.values():
        status = coordinator.data

        # for (
        #     translation_key,
        #     sensor_name,
        #     device_class,
        #     unit,
        #     entity_category,
        #     state_class,
        #     enabled_default,
        # ) in sensor_configs:
        #     sensor = EntitySensor(
        #         coordinator=coordinator,
        #         translation_key=translation_key,
        #         sensor_name=sensor_name,
        #         device_class=device_class,
        #         unit_of_measurement=unit,
        #         is_diagnostic=False,
        #         entity_category=entity_category,
        #         state_class=state_class,
        #         enabled_default=enabled_default,
        #     )
        #     entities.append(sensor)

        for zone in status.remote_zone_info:
            if zone.exists:
                entities.append(ZoneTemperatureSensor(coordinator, zone))
                entities.append(ZoneHumiditySensor(coordinator, zone))

        # for peripheral in status.peripherals:
        #     entities.append(PeripheralBatterySensor(coordinator, peripheral))
        #     entities.append(PeripheralTemperatureSensor(coordinator, peripheral))
        #     entities.append(PeripheralHumiditySensor(coordinator, peripheral))

        # Add all sensors
        async_add_entities(entities)


class BaseZoneSensor(CoordinatorEntity[ActronAirSystemCoordinator], SensorEntity):
    """Base class for Actron Air sensors."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        zone: ActronAirZone,
    ) -> None:
        """Initialise the sensor entity."""
        super().__init__(coordinator)
        self._serial_number = coordinator.serial_number
        self.zone = zone
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, f"{self._serial_number}_zone_{zone.zone_id}")},
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return not self.coordinator.is_device_stale()


class ZoneHumiditySensor(BaseZoneSensor):
    """Humidity sensor for Actron Air zone."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "zone_humidity"

    def __init__(self, coordinator: ActronAirSystemCoordinator, zone) -> None:
        """Initialize the humidity sensor."""
        super().__init__(coordinator, zone)
        self._attr_unique_id: str = (
            f"{self._serial_number}_zone_{zone.zone_id}_zone_humidity"
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return getattr(self.zone, "live_humidity_pc", None)


class ZoneTemperatureSensor(BaseZoneSensor):
    """Temperature sensor for Actron Air zone."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "zone_temperature"

    def __init__(
        self, coordinator: ActronAirSystemCoordinator, zone: ActronAirZone
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, zone)
        self._attr_unique_id: str = (
            f"{self._serial_number}_zone_{zone.zone_id}_zone_temperature"
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return getattr(self.zone, "live_temp_c", None)


# class BasePeripheralSensor(CoordinatorEntity, Entity):
#     """Base class for Actron Air sensors."""

#     _attr_has_entity_name = True

#     def __init__(
#         self,
#         coordinator: ActronAirSystemCoordinator,
#         peripheral: ActronAirPeripheral,
#         translation_key: str,
#         state_key: str,
#         device_class: SensorDeviceClass,
#         unit_of_measurement,
#         entity_category=None,
#         enabled_default=True,
#     ) -> None:
#         """Initialize the sensor."""
#         super().__init__(coordinator)
#         self._ac_serial = coordinator.serial_number
#         self._peripheral_id = peripheral.logical_address
#         self._state_key = state_key
#         self._serial_number = peripheral.serial_number
#         self._entity_category = entity_category
#         self._enabled_default = enabled_default
#         self._attr_device_class = device_class
#         self._attr_unit_of_measurement = unit_of_measurement
#         self._attr_translation_key = translation_key
#         self._attr_unique_id: str = f"{self._serial_number}_{translation_key}"

#         suggested_area = None
#         if hasattr(peripheral, "zones") and len(peripheral.zones) == 1:
#             zone = peripheral.zones[0]
#             if hasattr(zone, "title") and zone.title:
#                 suggested_area = zone.title

#         self._attr_device_info: DeviceInfo = DeviceInfo(
#             identifiers={(DOMAIN, self._serial_number)},
#             name=f"{peripheral.device_type} {peripheral.logical_address}",
#             manufacturer="Actron Air",
#             model=peripheral.device_type,
#             suggested_area=suggested_area,
#         )

#     @property
#     def _peripheral(self) -> ActronAirPeripheral:
#         """Get the current peripheral data from the coordinator."""
#         for peripheral in self.coordinator.data.peripherals:
#             if peripheral.logical_address == self._peripheral_id:
#                 return peripheral
#         return None

#     @property
#     def available(self) -> bool:
#         """Return True if entity is available."""
#         return not self.coordinator.is_device_stale()

#     @property
#     def state(self) -> str | None:
#         """Return the state of the sensor."""
#         return getattr(self._peripheral, self._state_key, None)

#     @property
#     def entity_category(self) -> EntityCategory | None:
#         """Return the entity category."""
#         return self._entity_category

#     @property
#     def entity_registry_enabled_default(self) -> bool:
#         """Return if the entity should be enabled when first added to the entity registry."""
#         return self._enabled_default


# class PeripheralBatterySensor(BasePeripheralSensor):
#     """Battery sensor for Actron Air zone."""

#     def __init__(
#         self, coordinator: ActronAirSystemCoordinator, peripheral: ActronAirPeripheral
#     ) -> None:
#         """Initialize the battery sensor."""
#         super().__init__(
#             coordinator,
#             peripheral,
#             "battery",
#             "battery_level",
#             SensorDeviceClass.BATTERY,
#             PERCENTAGE,
#             entity_category=DIAGNOSTIC_CATEGORY,
#             enabled_default=True,
#         )


# class PeripheralTemperatureSensor(BasePeripheralSensor):
#     """Temperature sensor for Actron Air zone."""

#     def __init__(
#         self, coordinator: ActronAirSystemCoordinator, peripheral: ActronAirPeripheral
#     ) -> None:
#         """Initialize the temperature sensor."""
#         super().__init__(
#             coordinator,
#             peripheral,
#             "temperature",
#             "temperature",
#             SensorDeviceClass.TEMPERATURE,
#             UnitOfTemperature.CELSIUS,
#         )


# class PeripheralHumiditySensor(BasePeripheralSensor):
#     """Humidity sensor for Actron Air zone."""

#     def __init__(
#         self, coordinator: ActronAirSystemCoordinator, peripheral: ActronAirPeripheral
#     ) -> None:
#         """Initialize the humidity sensor."""
#         super().__init__(
#             coordinator,
#             peripheral,
#             "humidity",
#             "humidity",
#             SensorDeviceClass.HUMIDITY,
#             PERCENTAGE,
#         )


# class BaseEntitySensor(CoordinatorEntity[ActronAirSystemCoordinator], SensorEntity):
#     """Base class for Actron Air sensors."""

#     _attr_has_entity_name = True
#     _attr_entity_registry_enabled_default = True

#     def __init__(
#         self,
#         coordinator: ActronAirSystemCoordinator,
#     ) -> None:
#         """Initialise the sensor entity."""
#         super().__init__(coordinator)
#         self._serial_number = coordinator.serial_number
#         self._attr_device_info: DeviceInfo = DeviceInfo(
#             identifiers={(DOMAIN, self._serial_number)},
#         )

#     @property
#     def available(self) -> bool:
#         """Return True if entity is available."""
#         return not self.coordinator.is_device_stale()
