"""Support for Homekit sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from aiohomekit.model import Accessory, Transport
from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes
from aiohomekit.model.characteristics.const import (
    CurrentAirPurifierStateValues,
    ThreadNodeCapabilities,
    ThreadStatus,
)
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_last_service_info,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import CharacteristicEntity, HomeKitEntity
from .utils import folded_name


@dataclass(frozen=True)
class HomeKitSensorEntityDescription(SensorEntityDescription):
    """Describes Homekit sensor."""

    probe: Callable[[Characteristic], bool] | None = None
    format: Callable[[Characteristic], str] | None = None
    enum: dict[IntEnum, str] | None = None


def thread_node_capability_to_str(char: Characteristic) -> str:
    """Return the thread device type as a string.

    The underlying value is a bitmask, but we want to turn that to
    a human readable string. Some devices will have multiple capabilities.
    For example, an NL55 is SLEEPY | MINIMAL. In that case we return the
    "best" capability.

    https://openthread.io/guides/thread-primer/node-roles-and-types
    """

    val = ThreadNodeCapabilities(char.value)

    if val & ThreadNodeCapabilities.BORDER_ROUTER_CAPABLE:
        # can act as a bridge between thread network and e.g. WiFi
        return "border_router_capable"

    if val & ThreadNodeCapabilities.ROUTER_ELIGIBLE:
        # radio always on, can be a router
        return "router_eligible"

    if val & ThreadNodeCapabilities.FULL:
        # radio always on, but can't be a router
        return "full"

    if val & ThreadNodeCapabilities.MINIMAL:
        # transceiver always on, does not need to poll for messages from its parent
        return "minimal"

    if val & ThreadNodeCapabilities.SLEEPY:
        # normally disabled, wakes on occasion to poll for messages from its parent
        return "sleepy"

    # Device has no known thread capabilities
    return "none"


def thread_status_to_str(char: Characteristic) -> str:
    """Return the thread status as a string.

    The underlying value is a bitmask, but we want to turn that to
    a human readable string. So we check the flags in order. E.g. BORDER_ROUTER implies
    ROUTER, so its more important to show that value.
    """

    val = ThreadStatus(char.value)

    if val & ThreadStatus.BORDER_ROUTER:
        # Device has joined the Thread network and is participating
        # in routing between mesh nodes.
        # It's also the border router - bridging the thread network
        # to WiFI/Ethernet/etc
        return "border_router"

    if val & ThreadStatus.LEADER:
        # Device has joined the Thread network and is participating
        # in routing between mesh nodes.
        # It's also the leader. There's only one leader and it manages
        # which nodes are routers.
        return "leader"

    if val & ThreadStatus.ROUTER:
        # Device has joined the Thread network and is participating
        # in routing between mesh nodes.
        return "router"

    if val & ThreadStatus.CHILD:
        # Device has joined the Thread network as a child
        # It's not participating in routing between mesh nodes
        return "child"

    if val & ThreadStatus.JOINING:
        # Device is currently joining its Thread network
        return "joining"

    if val & ThreadStatus.DETACHED:
        # Device is currently unable to reach its Thread network
        return "detached"

    # Must be ThreadStatus.DISABLED
    # Device is not currently connected to Thread and will not try to.
    return "disabled"


SIMPLE_SENSOR: dict[str, HomeKitSensorEntityDescription] = {
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_WATT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_WATT,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS,
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS_20: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS_20,
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_KW_HOUR: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_KW_HOUR,
        name="Energy kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    CharacteristicsTypes.VENDOR_EVE_ENERGY_WATT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_ENERGY_WATT,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    CharacteristicsTypes.VENDOR_EVE_ENERGY_KW_HOUR: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_ENERGY_KW_HOUR,
        name="Energy kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    CharacteristicsTypes.VENDOR_EVE_ENERGY_VOLTAGE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_ENERGY_VOLTAGE,
        name="Volts",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    CharacteristicsTypes.VENDOR_EVE_ENERGY_AMPERE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_ENERGY_AMPERE,
        name="Amps",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY_2: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY_2,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    CharacteristicsTypes.VENDOR_EVE_DEGREE_AIR_PRESSURE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_DEGREE_AIR_PRESSURE,
        name="Air Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    CharacteristicsTypes.VENDOR_VOCOLINC_OUTLET_ENERGY: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_VOCOLINC_OUTLET_ENERGY,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    CharacteristicsTypes.TEMPERATURE_CURRENT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.TEMPERATURE_CURRENT,
        name="Current Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        # This sensor is only for temperature characteristics that are not part
        # of a temperature sensor service.
        probe=(lambda char: char.service.type != ServicesTypes.TEMPERATURE_SENSOR),
    ),
    CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
        name="Current Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        # This sensor is only for humidity characteristics that are not part
        # of a humidity sensor service.
        probe=(lambda char: char.service.type != ServicesTypes.HUMIDITY_SENSOR),
    ),
    CharacteristicsTypes.AIR_QUALITY: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.AIR_QUALITY,
        name="Air Quality",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CharacteristicsTypes.DENSITY_PM25: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_PM25,
        name="PM2.5 Density",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_PM10: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_PM10,
        name="PM10 Density",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_OZONE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_OZONE,
        name="Ozone Density",
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_NO2: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_NO2,
        name="Nitrogen Dioxide Density",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_SO2: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_SO2,
        name="Sulphur Dioxide Density",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_VOC: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_VOC,
        name="Volatile Organic Compound Density",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.THREAD_NODE_CAPABILITIES: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.THREAD_NODE_CAPABILITIES,
        name="Thread Capabilities",
        entity_category=EntityCategory.DIAGNOSTIC,
        format=thread_node_capability_to_str,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "border_router_capable",
            "full",
            "minimal",
            "none",
            "router_eligible",
            "sleepy",
        ],
        translation_key="thread_node_capabilities",
    ),
    CharacteristicsTypes.THREAD_STATUS: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.THREAD_STATUS,
        name="Thread Status",
        entity_category=EntityCategory.DIAGNOSTIC,
        format=thread_status_to_str,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "border_router",
            "child",
            "detached",
            "disabled",
            "joining",
            "leader",
            "router",
        ],
        translation_key="thread_status",
    ),
    CharacteristicsTypes.AIR_PURIFIER_STATE_CURRENT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.AIR_PURIFIER_STATE_CURRENT,
        name="Air Purifier Status",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        enum={
            CurrentAirPurifierStateValues.INACTIVE: "inactive",
            CurrentAirPurifierStateValues.IDLE: "idle",
            CurrentAirPurifierStateValues.ACTIVE: "purifying",
        },
        translation_key="air_purifier_state_current",
    ),
    CharacteristicsTypes.VENDOR_NETATMO_NOISE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_NETATMO_NOISE,
        name="Noise",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
    ),
    CharacteristicsTypes.FILTER_LIFE_LEVEL: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.FILTER_LIFE_LEVEL,
        name="Filter lifetime",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    CharacteristicsTypes.VENDOR_EVE_THERMO_VALVE_POSITION: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_THERMO_VALVE_POSITION,
        name="Valve position",
        icon="mdi:pipe-valve",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
}


class HomeKitSensor(HomeKitEntity, SensorEntity):
    """Representation of a HomeKit sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str | None:
        """Return the name of the device."""
        full_name = super().name
        default_name = self.default_name
        if (
            default_name
            and full_name
            and folded_name(default_name) not in folded_name(full_name)
        ):
            return f"{full_name} {default_name}"
        return full_name


class HomeKitHumiditySensor(HomeKitSensor):
    """Representation of a Homekit humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT]

    @property
    def default_name(self) -> str:
        """Return the default name of the device."""
        return "Humidity"

    @property
    def native_value(self) -> float:
        """Return the current humidity."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)


class HomeKitTemperatureSensor(HomeKitSensor):
    """Representation of a Homekit temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.TEMPERATURE_CURRENT]

    @property
    def default_name(self) -> str:
        """Return the default name of the device."""
        return "Temperature"

    @property
    def native_value(self) -> float:
        """Return the current temperature in Celsius."""
        return self.service.value(CharacteristicsTypes.TEMPERATURE_CURRENT)


class HomeKitLightSensor(HomeKitSensor):
    """Representation of a Homekit light level sensor."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_native_unit_of_measurement = LIGHT_LUX

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.LIGHT_LEVEL_CURRENT]

    @property
    def default_name(self) -> str:
        """Return the default name of the device."""
        return "Light Level"

    @property
    def native_value(self) -> int:
        """Return the current light level in lux."""
        return self.service.value(CharacteristicsTypes.LIGHT_LEVEL_CURRENT)


class HomeKitCarbonDioxideSensor(HomeKitSensor):
    """Representation of a Homekit Carbon Dioxide sensor."""

    _attr_device_class = SensorDeviceClass.CO2
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CARBON_DIOXIDE_LEVEL]

    @property
    def default_name(self) -> str:
        """Return the default name of the device."""
        return "Carbon Dioxide"

    @property
    def native_value(self) -> int:
        """Return the current CO2 level in ppm."""
        return self.service.value(CharacteristicsTypes.CARBON_DIOXIDE_LEVEL)


class HomeKitBatterySensor(HomeKitSensor):
    """Representation of a Homekit battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [
            CharacteristicsTypes.BATTERY_LEVEL,
            CharacteristicsTypes.STATUS_LO_BATT,
            CharacteristicsTypes.CHARGING_STATE,
        ]

    @property
    def default_name(self) -> str:
        """Return the default name of the device."""
        return "Battery"

    @property
    def icon(self) -> str:
        """Return the sensor icon."""
        native_value = self.native_value
        if not self.available or native_value is None:
            return "mdi:battery-unknown"

        # This is similar to the logic in helpers.icon, but we have delegated the
        # decision about what mdi:battery-alert is to the device.
        icon = "mdi:battery"
        is_charging = self.is_charging
        if is_charging and native_value > 10:
            percentage = int(round(native_value / 20 - 0.01)) * 20
            icon += f"-charging-{percentage}"
        elif is_charging:
            icon += "-outline"
        elif self.is_low_battery:
            icon += "-alert"
        elif native_value < 95:
            percentage = max(int(round(native_value / 10 - 0.01)) * 10, 10)
            icon += f"-{percentage}"

        return icon

    @property
    def is_low_battery(self) -> bool:
        """Return true if battery level is low."""
        return self.service.value(CharacteristicsTypes.STATUS_LO_BATT) == 1

    @property
    def is_charging(self) -> bool:
        """Return true if currently charing."""
        # 0 = not charging
        # 1 = charging
        # 2 = not chargeable
        return self.service.value(CharacteristicsTypes.CHARGING_STATE) == 1

    @property
    def native_value(self) -> int:
        """Return the current battery level percentage."""
        return self.service.value(CharacteristicsTypes.BATTERY_LEVEL)


class SimpleSensor(CharacteristicEntity, SensorEntity):
    """A simple sensor for a single characteristic.

    This may be an additional secondary entity that is part of another service. An
    example is a switch that has an energy sensor.

    These *have* to have a different unique_id to the normal sensors as there could
    be multiple entities per HomeKit service (this was not previously the case).
    """

    entity_description: HomeKitSensorEntityDescription

    def __init__(
        self,
        conn: HKDevice,
        info: ConfigType,
        char: Characteristic,
        description: HomeKitSensorEntityDescription,
    ) -> None:
        """Initialise a secondary HomeKit characteristic sensor."""
        self.entity_description = description
        if self.entity_description.enum:
            self._attr_options = list(self.entity_description.enum.values())
        super().__init__(conn, info, char)

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        if name := self.accessory.name:
            return f"{name} {self.entity_description.name}"
        return f"{self.entity_description.name}"

    @property
    def native_value(self) -> str | int | float:
        """Return the current sensor value."""
        if self.entity_description.enum:
            return self.entity_description.enum[self._char.value]
        if self.entity_description.format:
            return self.entity_description.format(self._char)
        return self._char.value


ENTITY_TYPES = {
    ServicesTypes.HUMIDITY_SENSOR: HomeKitHumiditySensor,
    ServicesTypes.TEMPERATURE_SENSOR: HomeKitTemperatureSensor,
    ServicesTypes.LIGHT_SENSOR: HomeKitLightSensor,
    ServicesTypes.CARBON_DIOXIDE_SENSOR: HomeKitCarbonDioxideSensor,
    ServicesTypes.BATTERY_SERVICE: HomeKitBatterySensor,
}

# Only create the entity if it has the required characteristic
REQUIRED_CHAR_BY_TYPE = {
    ServicesTypes.BATTERY_SERVICE: CharacteristicsTypes.BATTERY_LEVEL,
}


class RSSISensor(HomeKitEntity, SensorEntity):
    """HomeKit Controller RSSI sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_should_poll = False

    def __init__(self, accessory: HKDevice, devinfo: ConfigType) -> None:
        """Initialise a HomeKit Controller RSSI sensor."""
        super().__init__(accessory, devinfo)
        self._attr_unique_id = f"{accessory.unique_id}_rssi"

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return []

    @property
    def available(self) -> bool:
        """Return if the bluetooth device is available."""
        address = self._accessory.pairing_data["AccessoryAddress"]
        return async_ble_device_from_address(self.hass, address) is not None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Signal strength"

    @property
    def old_unique_id(self) -> str:
        """Return the old ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-rssi"

    @property
    def native_value(self) -> int | None:
        """Return the current rssi value."""
        address = self._accessory.pairing_data["AccessoryAddress"]
        last_service_info = async_last_service_info(self.hass, address)
        return last_service_info.rssi if last_service_info else None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit sensors."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if not (entity_class := ENTITY_TYPES.get(service.type)):
            return False
        if (
            required_char := REQUIRED_CHAR_BY_TYPE.get(service.type)
        ) and not service.has(required_char):
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        entity: HomeKitSensor = entity_class(conn, info)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.SENSOR
        )
        async_add_entities([entity])
        return True

    conn.add_listener(async_add_service)

    @callback
    def async_add_characteristic(char: Characteristic) -> bool:
        if not (description := SIMPLE_SENSOR.get(char.type)):
            return False
        if description.probe and not description.probe(char):
            return False
        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}
        entity = SimpleSensor(conn, info, char, description)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.SENSOR
        )
        async_add_entities([entity])

        return True

    conn.add_char_factory(async_add_characteristic)

    @callback
    def async_add_accessory(accessory: Accessory) -> bool:
        if conn.pairing.transport != Transport.BLE:
            return False

        accessory_info = accessory.services.first(
            service_type=ServicesTypes.ACCESSORY_INFORMATION
        )
        assert accessory_info
        info = {"aid": accessory.aid, "iid": accessory_info.iid}
        entity = RSSISensor(conn, info)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.SENSOR
        )
        async_add_entities([entity])
        return True

    conn.add_accessory_factory(async_add_accessory)
