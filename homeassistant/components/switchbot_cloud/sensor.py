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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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

# {
#     'online': True,
#     'version': 'V1.7',
#     'switch1Status': 1,
#     'switch1Voltage': 234.5,
#     'switch1Power': 0,
#     'switch1ElectricCurrent': 3,
#     'switch1UsedElectricity': 0,
#     'switch2Status': 1,
#     'switch2Voltage': 234.5,
#     'switch2Power': 0,
#     'switch2ElectricCurrent': 3,
#     'switch2UsedElectricity': 0,
#     'deviceId': 'C04E30DF93A6',
#     'deviceType': 'Relay Switch 2PM',
#     'hubDeviceId': 'C04E30DF93A6'
# }


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

VOLTAGE_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_VOLTAGE,
    device_class=SensorDeviceClass.VOLTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
)

CURRENT_DESCRIPTION_IN_MA = SensorEntityDescription(
    key=SENSOR_TYPE_CURRENT,
    device_class=SensorDeviceClass.CURRENT,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
)

CURRENT_DESCRIPTION_IN_A = SensorEntityDescription(
    key=SENSOR_TYPE_CURRENT,
    device_class=SensorDeviceClass.CURRENT,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
)

CO2_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_CO2,
    device_class=SensorDeviceClass.CO2,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
)

SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES = {
    "Bot": (BATTERY_DESCRIPTION,),
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
        VOLTAGE_DESCRIPTION,
        CURRENT_DESCRIPTION_IN_MA,
    ),
    "Relay Switch 2PM": (
        POWER_DESCRIPTION,
        VOLTAGE_DESCRIPTION,
        CURRENT_DESCRIPTION_IN_MA,
    ),
    "Plug Mini (US)": (
        VOLTAGE_DESCRIPTION,
        CURRENT_DESCRIPTION_IN_A,
    ),
    "Plug Mini (JP)": (
        VOLTAGE_DESCRIPTION,
        CURRENT_DESCRIPTION_IN_A,
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
    "Smart Lock Pro": (BATTERY_DESCRIPTION,),
    "Smart Lock": (BATTERY_DESCRIPTION,),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    entities_list: list[SwitchBotCloudSensor] = []
    for device, coordinator in data.devices.sensors:
        for description in SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES[device.device_type]:
            entities_list.extend(
                [SwitchBotCloudSensor(data.api, device, coordinator, description)]
            )
    async_add_entities(entities_list)


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

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if not self.coordinator.data:
            return
        self._attr_native_value = self.coordinator.data.get(self.entity_description.key)


class SwitchBotCloudRelaySwitch2PMSensor(SwitchBotCloudEntity, SensorEntity):
    """Representation of a SwitchBot Cloud Relay Switch 2PM sensor entity."""

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

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if not self.coordinator.data:
            return
        name: str | None = (
            self._attr_device_info.get("name") if self._attr_device_info else None
        )
        if name is None:
            return
        index = int(name.split("")[-1])
        self._reshape_coordinator_data(index)

        self._attr_native_value = self.coordinator.data.get(self.entity_description.key)

    def _reshape_coordinator_data(self, target: int) -> int:
        assert target in [1, 2]
        return target
