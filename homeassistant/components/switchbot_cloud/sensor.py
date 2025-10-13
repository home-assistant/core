"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from switchbot_api import Device, Remote, SwitchBotAPI

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
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
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
SENSOR_TYPE_POWER_CONSUMPTION = "weight"
SENSOR_TYPE_DURATION_OF_USED = "electricityOfDay"
SENSOR_TYPE_USED_ELECTRICITY = "usedElectricity"
SENSOR_TYPE_LIGHTLEVEL = "lightLevel"


RELAY_SWITCH_2PM_SENSOR_TYPE_POWER = "Power"
RELAY_SWITCH_2PM_SENSOR_TYPE_VOLTAGE = "Voltage"
RELAY_SWITCH_2PM_SENSOR_TYPE_CURRENT = "ElectricCurrent"
RELAY_SWITCH_2PM_SENSOR_TYPE_ELECTRICITY = "UsedElectricity"


@dataclass(frozen=True, kw_only=True)
class SwitchbotCloudSensorEntityDescription(SensorEntityDescription):
    """Plug Mini Eu UsedElectricity Sensor EntityDescription."""

    value_fn: Callable[[Any], Any] = lambda value: value


USED_ELECTRICITY_DESCRIPTION = SwitchbotCloudSensorEntityDescription(
    key=SENSOR_TYPE_USED_ELECTRICITY,
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    suggested_display_precision=2,
    value_fn=lambda data: (data.get(SENSOR_TYPE_USED_ELECTRICITY) or 0) / 60000,
)

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

POWER_CONSUMPTION_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_POWER_CONSUMPTION,
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfPower.WATT,
)

RELAY_SWITCH_2PM_POWER_DESCRIPTION = SensorEntityDescription(
    key=RELAY_SWITCH_2PM_SENSOR_TYPE_POWER,
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfPower.WATT,
)

RELAY_SWITCH_2PM_VOLTAGE_DESCRIPTION = SensorEntityDescription(
    key=RELAY_SWITCH_2PM_SENSOR_TYPE_VOLTAGE,
    device_class=SensorDeviceClass.VOLTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
)

RELAY_SWITCH_2PM_CURRENT_DESCRIPTION = SensorEntityDescription(
    key=RELAY_SWITCH_2PM_SENSOR_TYPE_CURRENT,
    device_class=SensorDeviceClass.CURRENT,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
)

RELAY_SWITCH_2PM_ElECTRICITY_DESCRIPTION = SensorEntityDescription(
    key=RELAY_SWITCH_2PM_SENSOR_TYPE_ELECTRICITY,
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
)

LIGHTLEVEL_DESCRIPTION = SensorEntityDescription(
    key="lightLevel",
    translation_key="light_level",
    state_class=SensorStateClass.MEASUREMENT,
)

SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES = {
    "Bot": (BATTERY_DESCRIPTION,),
    "Battery Circulator Fan": (BATTERY_DESCRIPTION,),
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
    "Plug Mini (US)": (
        VOLTAGE_DESCRIPTION,
        CURRENT_DESCRIPTION_IN_MA,
        POWER_CONSUMPTION_DESCRIPTION,
    ),
    "Plug Mini (JP)": (
        VOLTAGE_DESCRIPTION,
        CURRENT_DESCRIPTION_IN_MA,
        POWER_CONSUMPTION_DESCRIPTION,
    ),
    "Plug Mini (EU)": (
        POWER_DESCRIPTION,
        VOLTAGE_DESCRIPTION,
        CURRENT_DESCRIPTION_IN_MA,
        USED_ELECTRICITY_DESCRIPTION,
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
    "Smart Lock": (BATTERY_DESCRIPTION,),
    "Smart Lock Lite": (BATTERY_DESCRIPTION,),
    "Smart Lock Pro": (BATTERY_DESCRIPTION,),
    "Smart Lock Ultra": (BATTERY_DESCRIPTION,),
    "Relay Switch 2PM": (
        RELAY_SWITCH_2PM_POWER_DESCRIPTION,
        RELAY_SWITCH_2PM_VOLTAGE_DESCRIPTION,
        RELAY_SWITCH_2PM_CURRENT_DESCRIPTION,
        RELAY_SWITCH_2PM_ElECTRICITY_DESCRIPTION,
    ),
    "Curtain": (BATTERY_DESCRIPTION,),
    "Curtain3": (BATTERY_DESCRIPTION,),
    "Roller Shade": (BATTERY_DESCRIPTION,),
    "Blind Tilt": (BATTERY_DESCRIPTION,),
    "Hub 3": (
        TEMPERATURE_DESCRIPTION,
        HUMIDITY_DESCRIPTION,
        LIGHTLEVEL_DESCRIPTION,
    ),
    "Motion Sensor": (BATTERY_DESCRIPTION,),
    "Contact Sensor": (BATTERY_DESCRIPTION,),
    "Water Detector": (BATTERY_DESCRIPTION,),
    "Humidifier": (TEMPERATURE_DESCRIPTION,),
    "Climate Panel": (
        TEMPERATURE_DESCRIPTION,
        HUMIDITY_DESCRIPTION,
        BATTERY_DESCRIPTION,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    entities: list[SwitchBotCloudSensor] = []
    for device, coordinator in data.devices.sensors:
        for description in SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES[device.device_type]:
            if device.device_type == "Relay Switch 2PM":
                entities.append(
                    SwitchBotCloudRelaySwitch2PMSensor(
                        data.api, device, coordinator, description, "1"
                    )
                )
                entities.append(
                    SwitchBotCloudRelaySwitch2PMSensor(
                        data.api, device, coordinator, description, "2"
                    )
                )
            else:
                entities.append(
                    _async_make_entity(data.api, device, coordinator, description)
                )
    async_add_entities(entities)


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


class SwitchBotCloudRelaySwitch2PMSensor(SwitchBotCloudSensor):
    """Representation of a SwitchBot Cloud Relay Switch 2PM sensor entity."""

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device,
        coordinator: SwitchBotCoordinator,
        description: SensorEntityDescription,
        channel: str,
    ) -> None:
        """Initialize SwitchBot Cloud sensor entity."""
        super().__init__(api, device, coordinator, description)

        self.entity_description = description
        self._channel = channel
        self._attr_unique_id = f"{device.device_id}-{description.key}-{channel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device.device_name}-channel-{channel}")},
            manufacturer="SwitchBot",
            model=device.device_type,
            model_id="RelaySwitch2PM",
            name=f"{device.device_name} Channel {channel}",
        )

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if not self.coordinator.data:
            return
        self._attr_native_value = self.coordinator.data.get(
            f"switch{self._channel}{self.entity_description.key.strip()}"
        )


@callback
def _async_make_entity(
    api: SwitchBotAPI,
    device: Device | Remote,
    coordinator: SwitchBotCoordinator,
    description: SensorEntityDescription,
) -> SwitchBotCloudSensor:
    """Make a SwitchBotCloudSensor or SwitchBotCloudRelaySwitch2PMSensor."""
    return SwitchBotCloudSensor(api, device, coordinator, description)
