"""waterkotte sensor platform."""

from pywaterkotte.ecotouch import EcotouchTags, TagData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcotouchCoordinator
from .const import DOMAIN
from .entity import EcotouchEntity

SENSOR_DESCRIPTIONS = {
    EcotouchTags.TEMPERATURE_WATER: SensorEntityDescription(
        key="water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:water-thermometer",
        native_unit_of_measurement=EcotouchTags.TEMPERATURE_WATER.unit,
    ),
    EcotouchTags.TEMPERATURE_OUTSIDE: SensorEntityDescription(
        key="outside_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:sun-thermometer-outline",
        native_unit_of_measurement=EcotouchTags.TEMPERATURE_OUTSIDE.unit,
    ),
    EcotouchTags.TEMPERATURE_OUTSIDE_1H: SensorEntityDescription(
        key="outside_temperature_1h",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:sun-thermometer-outline",
        native_unit_of_measurement=EcotouchTags.TEMPERATURE_OUTSIDE_1H.unit,
    ),
    EcotouchTags.TEMPERATURE_OUTSIDE_24H: SensorEntityDescription(
        key="outside_temperature_24h",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:sun-thermometer-outline",
        native_unit_of_measurement=EcotouchTags.TEMPERATURE_OUTSIDE_24H.unit,
    ),
    EcotouchTags.TEMPERATURE_SOURCE_IN: SensorEntityDescription(
        key="source_in_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=EcotouchTags.TEMPERATURE_SOURCE_IN.unit,
    ),
    EcotouchTags.TEMPERATURE_SOURCE_OUT: SensorEntityDescription(
        key="source_out_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=EcotouchTags.TEMPERATURE_SOURCE_OUT.unit,
    ),
    EcotouchTags.ELECTRICAL_POWER: SensorEntityDescription(
        key="electrical_power",
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=EcotouchTags.ELECTRICAL_POWER.unit,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create waterkotte_heatpump sensor entities."""
    coordinator: EcotouchCoordinator = hass.data[DOMAIN][entry.entry_id]

    def get_device_info() -> DeviceInfo:
        heatpump_type = coordinator.heatpump.read_value(EcotouchTags.HEATPUMP_TYPE)
        serial_nr = coordinator.heatpump.read_value(EcotouchTags.SERIAL_NUMBER)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{serial_nr:08d}")},
            name="heatpump",
            manufacturer="Waterkotte GmbH",
            model=coordinator.heatpump.decode_heatpump_series(heatpump_type),
            sw_version="1.2.3",
            hw_version="13",
            configuration_url=f'http://{entry.data.get("host")}',
        )

    device_info = await hass.async_add_executor_job(get_device_info)

    entities = [
        EcotouchSensor(entry, coordinator, tag, sensor_config, device_info)
        for tag, sensor_config in SENSOR_DESCRIPTIONS.items()
    ]

    async_add_entities(entities)


class EcotouchSensor(EcotouchEntity, SensorEntity):
    """waterkotte_heatpump Sensor class."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: EcotouchCoordinator,
        tag: TagData,
        sensor_config: SensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self.entity_description = sensor_config
        super().__init__(coordinator, tag, config_entry, sensor_config, device_info)
