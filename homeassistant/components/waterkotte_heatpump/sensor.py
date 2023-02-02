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
        name="water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:water-thermometer",
        native_unit_of_measurement=EcotouchTags.TEMPERATURE_WATER.unit,
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create waterkotte_heatpump sensor entities."""
    coordinator: EcotouchCoordinator = hass.data[DOMAIN][entry.entry_id]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "00404366")},
        name="heatpump",
        manufacturer="Waterkotte GmbH",
        model="EcoTouch DS 5027 Ai",
        sw_version="1.2.3",
        hw_version="13",
        configuration_url=f'http://{entry.data.get("host")}',
    )

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
