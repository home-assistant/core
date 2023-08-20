"""Support for Flexit Nordic (BACnet) machine temperature sensors."""

from flexit_bacnet import FlexitBACnet

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, MODEL, NAME

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="outside_air_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        name="Outside air temperature",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Flexit Nordic ventilation machine sensors."""
    device = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        FlexitSensorEntity(
            entity_description,
            device,
        )
        for entity_description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class FlexitSensorEntity(SensorEntity):
    """Flexit ventilation machine sensor entity."""

    def __init__(
        self, entity_description: SensorEntityDescription, device: FlexitBACnet
    ) -> None:
        """Initialize the sensor."""
        self._device = device
        self.entity_description = entity_description

        self._attr_unique_id = f"{device.serial_number}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            name=NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_update(self) -> None:
        """Refresh unit state."""

    @property
    def native_value(self) -> float:
        """Return temperature."""
        return self._device.outside_air_temperature
