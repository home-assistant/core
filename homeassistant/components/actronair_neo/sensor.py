"""Sensor platform for Actron Air Neo integration."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import ACZone, ZonePeripheral
from .entity import (
    EntitySensor,
    PeripheralBatterySensor,
    PeripheralHumiditySensor,
    PeripheralTemperatureSensor,
    ZoneHumiditySensor,
    ZonePostionSensor,
    ZoneTemperatureSensor,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Actron Air Neo sensors."""
    instance = config_entry.runtime_data
    coordinator = instance.coordinator
    ac_unit = instance.ac_unit

    # Obtain AC Units
    status = coordinator.data

    # Diagnostic sensor configurations
    diagnostic_configs = [
        (
            ac_unit,
            "clean_filter",
            ["Alerts"],
            "CleanFilter",
            None,
            False,
        ),
        (
            ac_unit,
            "defrost_mode",
            ["Alerts"],
            "Defrosting",
            None,
            False,
        ),
        (
            ac_unit,
            "compressor_chasing_temperature",
            ["LiveAircon"],
            "CompressorChasingTemperature",
            SensorDeviceClass.TEMPERATURE,
            True,
        ),
        (
            ac_unit,
            "compressor_live_temperature",
            ["LiveAircon"],
            "CompressorLiveTemperature",
            SensorDeviceClass.TEMPERATURE,
            True,
        ),
        (
            ac_unit,
            "compressor_mode",
            ["LiveAircon"],
            "CompressorMode",
            None,
            True,
        ),
        (
            ac_unit,
            "system_on",
            ["UserAirconSettings"],
            "isOn",
            None,
            False,
        ),
        (
            ac_unit,
            "compressor_speed",
            ["LiveAircon", "OutdoorUnit"],
            "CompSpeed",
            SensorDeviceClass.SPEED,
            True,
        ),
        (
            ac_unit,
            "compressor_power",
            ["LiveAircon", "OutdoorUnit"],
            "CompPower",
            SensorDeviceClass.POWER,
            True,
        ),
        (
            ac_unit,
            "outdoor_temperature",
            ["MasterInfo"],
            "LiveOutdoorTemp_oC",
            SensorDeviceClass.TEMPERATURE,
            False,
        ),
        (
            ac_unit,
            "humidity",
            ["MasterInfo"],
            "LiveHumidity_pc",
            SensorDeviceClass.HUMIDITY,
            False,
        ),
    ]

    # Create diagnostic sensors
    ac_unit_sensors = []
    for (
        ac_unit,
        translation_key,
        path,
        key,
        unit,
        diagnostic_sensor,
    ) in diagnostic_configs:
        ac_unit_sensors.append(
            EntitySensor(
                coordinator,
                ac_unit,
                translation_key,
                path,
                key,
                ac_unit.device_info,
                unit,
                diagnostic_sensor,
            )
        )

    # Fetch Zones
    zones = status.get("RemoteZoneInfo", [])

    zone_sensors = []
    ac_zones = []

    # Create zones & sensors
    for zone_number, zone in enumerate(zones, start=1):
        if zone["NV_Exists"]:
            # Create zone device
            zone_name = zone["NV_Title"]
            ac_zone = ACZone(ac_unit, zone_number, zone_name)
            ac_zones.append(ac_zone)
            zone_sensors.extend(create_zone_sensors(coordinator, ac_zone))

    # Fetch Peripherals
    peripherals = status.get("AirconSystem", {}).get("Peripherals", [])

    for peripheral in peripherals:
        # Create zone sensor device
        logical_address = peripheral["LogicalAddress"]
        device_type = peripheral.get("DeviceType", None)
        zone_serial = peripheral["SerialNumber"]
        mac_address = peripheral["MACAddress"]
        zone_id = peripheral.get("ZoneAssignment")[0]
        firmware = peripheral.get("Firmware", {})
        installed_version = firmware.get("InstalledVersion", {})
        software_version = installed_version.get("NRF52", {})
        zone_assignment = ac_zones[zone_id - 1]
        zone_peripheral = ZonePeripheral(
            ac_unit,
            logical_address,
            zone_serial,
            mac_address,
            zone_assignment,
            device_type,
            software_version,
        )
        zone_sensors.extend(create_peripheral_sensors(coordinator, zone_peripheral))

    # Add all sensors
    async_add_entities(ac_unit_sensors + zone_sensors)


def create_zone_sensors(coordinator, ac_zone):
    """Create all sensors for a given zone device."""
    return [
        ZonePostionSensor(coordinator, ac_zone),
        ZoneTemperatureSensor(coordinator, ac_zone),
        ZoneHumiditySensor(coordinator, ac_zone),
    ]


def create_peripheral_sensors(coordinator, zone_peripheral):
    """Create all sensors for a given peripheral zone device."""
    return [
        PeripheralBatterySensor(coordinator, zone_peripheral),
        PeripheralTemperatureSensor(coordinator, zone_peripheral),
        PeripheralHumiditySensor(coordinator, zone_peripheral),
    ]
