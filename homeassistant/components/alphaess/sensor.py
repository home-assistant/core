"""Alpha ESS Sensor definitions."""
from typing import List

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, PERCENTAGE
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AlphaESSDataUpdateCoordinator
from .entity import AlphaESSSensorDescription
from .enums import AlphaESSNames

SENSOR_DESCRIPTIONS: List[AlphaESSSensorDescription] = [
    AlphaESSSensorDescription(
        key=AlphaESSNames.SolarProduction,
        name="Solar Production",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlphaESSSensorDescription(
        key=AlphaESSNames.SolarToBattery,
        name="Solar to Battery",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlphaESSSensorDescription(
        key=AlphaESSNames.SolarToGrid,
        name="Solar to Grid",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlphaESSSensorDescription(
        key=AlphaESSNames.SolarToLoad,
        name="Solar to Load",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlphaESSSensorDescription(
        key=AlphaESSNames.TotalLoad,
        name="Total Load",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlphaESSSensorDescription(
        key=AlphaESSNames.GridToLoad,
        name="Grid to Load",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlphaESSSensorDescription(
        key=AlphaESSNames.GridToBattery,
        name="Grid to Battery",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlphaESSSensorDescription(
        key=AlphaESSNames.StateOfCharge,
        name="State of Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AlphaESSSensorDescription(
        key=AlphaESSNames.Charge,
        name="Charge",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlphaESSSensorDescription(
        key=AlphaESSNames.Discharge,
        name="Discharge",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Defer sensor setup to the shared sensor module."""

    coordinator: AlphaESSDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[AlphaESSSensor] = []

    key_supported_states = {
        description.key: description for description in SENSOR_DESCRIPTIONS
    }

    for invertor in coordinator.data:
        serial = invertor
        for description in key_supported_states:
            entities.append(
                AlphaESSSensor(
                    coordinator, entry, serial, key_supported_states[description].name
                )
            )
    async_add_entities(entities)

    return


class AlphaESSSensor(CoordinatorEntity, SensorEntity):
    """Alpha ESS Base Sensor."""

    def __init__(self, coordinator, config, serial, name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config = config
        self._name = name
        self._serial = serial
        self._coordinator = coordinator

        for invertor in coordinator.data:
            serial = invertor
            if self._serial == serial:
                self._attr_device_info = DeviceInfo(
                    entry_type=DeviceEntryType.SERVICE,
                    identifiers={(DOMAIN, serial)},
                    manufacturer="AlphaESS",
                    model=coordinator.data[invertor]["Model"],
                    name=f"Alpha ESS Energy Statistics : {serial}",
                )

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self._config.entry_id}_{self._serial} - {self._name}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._serial} - {self._name}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        key_supported_states = {
            description.key: description for description in SENSOR_DESCRIPTIONS
        }
        return key_supported_states[self._name].native_unit_of_measurement

    @property
    def native_value(self):
        """Return the state of the resources."""
        return self._coordinator.data[self._serial][self._name]
