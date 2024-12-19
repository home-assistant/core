"""Platform for sensor integration."""

from switchbot_api import Device, SwitchBotAPI

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity

SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_BATTERY = "battery"
SENSOR_TYPE_CO2 = "CO2"
SENSOR_TYPE_POWER = "power"
SENSOR_TYPE_VOLTAGE = "voltage"
SENSOR_TYPE_CURRENT = "electricCurrent"

TEMPERATURE_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_TEMPERATURE,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
)

HUMIDITY_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_HUMIDITY,
    device_class=SensorDeviceClass.HUMIDITY,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
)

BATTERY_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_BATTERY,
    device_class=SensorDeviceClass.BATTERY,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
)

POWER_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_POWER,
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfPower.WATT,
)

VOLATGE_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_VOLTAGE,
    device_class=SensorDeviceClass.VOLTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
)

CURRENT_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_CURRENT,
    device_class=SensorDeviceClass.CURRENT,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
)

CO2_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_CO2,
    device_class=SensorDeviceClass.CO2,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
)

SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES = {
    "Meter": (
        TEMPERATURE_DESCRIPTION,
        HUMIDITY_DESCRIPTION,
        BATTERY_DESCRIPTION,
    ),
    "MeterPlus": (
        TEMPERATURE_DESCRIPTION,
        HUMIDITY_DESCRIPTION,
        BATTERY_DESCRIPTION,
    ),
    "WoIOSensor": (
        TEMPERATURE_DESCRIPTION,
        HUMIDITY_DESCRIPTION,
        BATTERY_DESCRIPTION,
    ),
    "Relay Switch 1PM": (
        POWER_DESCRIPTION,
        VOLATGE_DESCRIPTION,
        CURRENT_DESCRIPTION,
    ),
    "Hub 2": (
        TEMPERATURE_DESCRIPTION,
        HUMIDITY_DESCRIPTION,
    ),
    "MeterPro": (
        TEMPERATURE_DESCRIPTION,
        HUMIDITY_DESCRIPTION,
        BATTERY_DESCRIPTION,
    ),
    "MeterPro(CO2)": (
        TEMPERATURE_DESCRIPTION,
        HUMIDITY_DESCRIPTION,
        BATTERY_DESCRIPTION,
        CO2_DESCRIPTION,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]

    async_add_entities(
        SwitchBotCloudSensor(data.api, device, coordinator, description)
        for device, coordinator in data.devices.sensors
        for description in SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES[device.device_type]
    )


class SwitchBotCloudSensor(SwitchBotCloudEntity, SensorEntity):
    """Representation of a SwitchBot Cloud sensor entity."""

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device,
        coordinator: SwitchBotCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize SwitchBot Cloud sensor entity."""
        super().__init__(api, device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device.device_id}_{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            return
        self._attr_native_value = self.coordinator.data.get(self.entity_description.key)
        self.async_write_ha_state()
