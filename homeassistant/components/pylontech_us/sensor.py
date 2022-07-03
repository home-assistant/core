"""Support for powerwall sensors."""
from __future__ import annotations

from dataclasses import dataclass

from pylontech import PylontechStack

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # CONF_PORT,; ELECTRIC_CURRENT_AMPERE,; ELECTRIC_POTENTIAL_VOLT,
    PERCENTAGE,
    POWER_KILO_WATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import PylontechCoordinator
from .const import DOMAIN

# @dataclass
# class PylontechRequiredKeysMixin:
#    """Mixin for required keys."""
# key: str
# icon: str
# value_fn: Callable[float]


@dataclass
class PylontechSensorEntityDescription(
    SensorEntityDescription,
    # PylontechRequiredKeysMixin
):
    """Describes Powerwall entity."""


def _get_instant_power() -> float:
    """Get the current value in kW."""
    return 0.0


PYLONTECH_STACK_SENSORS = (
    PylontechSensorEntityDescription(
        key="TotalCapacity_Ah",
        name="Pylontech_TotalCapacity_Ah",
        state_class=SensorStateClass.MEASUREMENT,
        device_class="Capacity",
        native_unit_of_measurement="Ah",
        entity_registry_enabled_default=True,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="RemainCapacity_Ah",
        name="Pylontech_RemainCapacity_Ah",
        state_class=SensorStateClass.MEASUREMENT,
        device_class="Capacity",
        native_unit_of_measurement="Ah",
        entity_registry_enabled_default=True,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="Remain_Percent",
        name="Pylontech_Remain_Percent",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=True,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="Power_kW",
        name="Pylontech_Power_kW",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_KILO_WATT,
        entity_registry_enabled_default=True,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="DischargePower_kW",
        name="Pylontech_DischargePower_kW",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_KILO_WATT,
        entity_registry_enabled_default=True,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="ChargePower_kW",
        name="Pylontech_ChargePower_kW",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_KILO_WATT,
        entity_registry_enabled_default=True,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    # PylontechSensorEntityDescription(
    #     key="instant_voltage",
    #     name="Average Voltage Now",
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    #     native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
    #     entity_registry_enabled_default=False,
    #     value_fn=_get_meter_average_voltage,
    # ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pylontech sensors."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SensorEntity] = []
    entities.extend(
        PylontechStackSensor(hass, coordinator, desc, config_entry.entry_id)
        for desc in PYLONTECH_STACK_SENSORS
    )
    factory = PylontechPackSensorFactory(hass, coordinator.get_result(), coordinator)
    new_entity: SensorEntity | None = None
    while True:
        new_entity = factory.create_next_sensor()
        if new_entity is None:
            break
        entities.append(new_entity)

    async_add_entities(entities)


class PylontechStackSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Pylontech sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PylontechCoordinator,
        desc: PylontechSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Stack summery value."""
        super().__init__(coordinator)
        self._hass = hass
        self._key = desc.key
        self._entry_id = entry_id
        result = self._hass.data[DOMAIN][self._entry_id].get_result()
        # result = await hass.async_add_executor_job(hub.update)
        self._attr_native_value = result["Calculated"][self._key]

        self._attr_name = desc.name
        self._attr_state_class = desc.state_class
        self._attr_native_unit_of_measurement = desc.native_unit_of_measurement
        self._attr_device_class = desc.device_class
        self._attr_icon = desc.icon
        self._attr_available = True
        self._attr_should_poll = True

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return "pylontech_stack_" + self._entry_id + "_" + str(self._attr_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # self._attr_is_on = self.coordinator.data[self.idx]["state"]
        # self.async_write_ha_state()
        result = self._hass.data[DOMAIN][self._entry_id].get_result()
        # result = await hass.async_add_executor_job(hub.update)
        self._attr_native_value = result["Calculated"][self._key]

        # super()._handle_coordinator_update()
        self._attr_available = True
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Poll battery stack."""
        await self.coordinator.async_request_refresh()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        # self._sensor.enabled = True

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # self._sensor.enabled = False


class PylontechPackSensorFactory:
    """Create all sensor entities for the packs."""

    def __init__(
        self,
        hass: HomeAssistant,
        data: PylontechStack,
        coordinator: PylontechCoordinator,
    ) -> None:
        """Sensor Factory constructor."""
        self._sensor_list = self._pylon_to_sensors(
            data=data, hass=hass, coordinator=coordinator
        )
        self._activated_sensor = 0

    def _pylon_to_sensors(
        self,
        data: PylontechStack,
        hass: HomeAssistant,
        coordinator: PylontechCoordinator,
    ) -> list[PylontechPackSensor]:
        print("----- pylon_to_sensors -----")
        return_list: list[PylontechPackSensor] = []
        pack_count = 1
        for data_element in data["SerialNumbers"]:
            print(data_element)
            sensor_name = "Pylontech_PackNr_" + str(pack_count) + "_Serial"
            sensor = PylontechPackSensor(
                hass=hass,
                coordinator=coordinator,
                name=str(sensor_name),
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=None,
                device_class="serial_number",  # SensorDeviceClass.,
                icon="mdi:numeric",
                key_main="SerialNumbers",
                key_sub=None,
                key_sub_nr=None,
                key_pack_nr=pack_count,
                entry_id=sensor_name,
                initial_result=data,
            )
            pack_count = pack_count + 1
        pack_count = 1
        for data_element in data["AnaloglList"]:
            print(data_element)
            element_count = 1
            for _ in data_element["CellVoltages"]:
                sensor_name = (
                    "Pylontech_PackNr_"
                    + str(pack_count)
                    + "_CellVoltage_"
                    + str(element_count)
                )
                sensor = PylontechPackSensor(
                    hass=hass,
                    coordinator=coordinator,
                    name=str(sensor_name),
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement="V",
                    device_class=SensorDeviceClass.VOLTAGE,
                    icon="mdi:lightning-bolt",
                    key_main="AnaloglList",
                    key_sub="CellVoltages",
                    key_sub_nr=element_count,
                    key_pack_nr=pack_count,
                    entry_id=sensor_name,
                    initial_result=data,
                )
                element_count = element_count + 1
                return_list.append(sensor)
            element_count = 1
            for _ in data_element["Temperatures"]:
                sensor_name = (
                    "Pylontech_PackNr_"
                    + str(pack_count)
                    + "_Temperature"
                    + str(element_count)
                )
                sensor = PylontechPackSensor(
                    hass=hass,
                    coordinator=coordinator,
                    name=str(sensor_name),
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement="°C",
                    device_class=SensorDeviceClass.TEMPERATURE,
                    icon="mdi:thermometer",
                    key_main="AnaloglList",
                    key_sub="Temperatures",
                    key_sub_nr=element_count,
                    key_pack_nr=pack_count,
                    entry_id=sensor_name,
                    initial_result=data,
                )
                element_count = element_count + 1
                return_list.append(sensor)
            sensor_name = "Pylontech_PackNr_" + str(pack_count) + "_Current"
            sensor = PylontechPackSensor(
                hass=hass,
                coordinator=coordinator,
                name=str(sensor_name),
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="A",
                device_class=SensorDeviceClass.CURRENT,
                icon="mdi:current-dc",
                key_main="AnaloglList",
                key_sub="Current",
                key_sub_nr=None,
                key_pack_nr=pack_count,
                entry_id=sensor_name,
                initial_result=data,
            )
            return_list.append(sensor)
            sensor_name = "Pylontech_PackNr_" + str(pack_count) + "_Voltage"
            sensor = PylontechPackSensor(
                hass=hass,
                coordinator=coordinator,
                name=str(sensor_name),
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="V",
                device_class=SensorDeviceClass.VOLTAGE,
                icon="mdi:lightning-bolt",
                key_main="AnaloglList",
                key_sub="Voltage",
                key_sub_nr=None,
                key_pack_nr=pack_count,
                entry_id=sensor_name,
                initial_result=data,
            )
            return_list.append(sensor)
            sensor_name = "Pylontech_PackNr_" + str(pack_count) + "_RemainCapacity"
            sensor = PylontechPackSensor(
                hass=hass,
                coordinator=coordinator,
                name=str(sensor_name),
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="Ah",
                device_class="capacity",
                icon="mdi:battery",
                key_main="AnaloglList",
                key_sub="RemainCapacity",
                key_sub_nr=None,
                key_pack_nr=pack_count,
                entry_id=sensor_name,
                initial_result=data,
            )
            return_list.append(sensor)
            sensor_name = "Pylontech_PackNr_" + str(pack_count) + "_ModuleTotalCapacity"
            sensor = PylontechPackSensor(
                hass=hass,
                coordinator=coordinator,
                name=str(sensor_name),
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="Ah",
                device_class="capacity",
                icon="mdi:battery",
                key_main="AnaloglList",
                key_sub="ModuleTotalCapacity",
                key_sub_nr=None,
                key_pack_nr=pack_count,
                entry_id=sensor_name,
                initial_result=data,
            )
            return_list.append(sensor)
            sensor_name = "Pylontech_PackNr_" + str(pack_count) + "_CycleNumber"
            sensor = PylontechPackSensor(
                hass=hass,
                coordinator=coordinator,
                name=str(sensor_name),
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=None,
                device_class="capacity",
                icon="mdi:battery",
                key_main="AnaloglList",
                key_sub="CycleNumber",
                key_sub_nr=None,
                key_pack_nr=pack_count,
                entry_id=sensor_name,
                initial_result=data,
            )
            return_list.append(sensor)
            pack_count = pack_count + 1

        return return_list

    def create_next_sensor(self) -> SensorEntity | None:
        """Return next sensor or None if no more left."""
        if self._activated_sensor < len(self._sensor_list):
            return_number = self._activated_sensor
            self._activated_sensor = self._activated_sensor + 1
            return self._sensor_list[return_number]
        return None


class PylontechPackSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Pylontech sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PylontechCoordinator,
        name: str,
        state_class: SensorStateClass | str | None,
        native_unit_of_measurement: str | None,
        device_class: SensorDeviceClass | str | None,
        icon: str | None,
        key_main: str,
        key_pack_nr: int,
        key_sub: str | None,
        key_sub_nr: int | None,
        entry_id: str,
        initial_result: PylontechStack,
    ) -> None:
        """Stack summery value."""
        if coordinator is not None:
            super().__init__(coordinator)
        self._hass = hass
        self._result = initial_result

        self._key_main = key_main
        self._key_pack_nr = key_pack_nr
        self._key_sub = key_sub
        self._key_sub_nr = key_sub_nr
        self._entry_id = entry_id

        # result = await hass.async_add_executor_job(hub.update)
        self._attr_native_value = str(self._get_key_result())
        print("initial result ", self._attr_native_value)

        self._attr_name = name
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_available = True
        self._attr_should_poll = True

    def _get_key_result(self):
        if self._result is None:
            return None
        if self._key_sub is None:
            return self._result[self._key_main][self._key_pack_nr - 1]
        if self._key_sub_nr is None:
            return self._result[self._key_main][self._key_pack_nr - 1][self._key_sub]
        return self._result[self._key_main][self._key_pack_nr - 1][self._key_sub][
            self._key_sub_nr - 1
        ]

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return "pylontech_stack_" + self._entry_id + "_" + str(self._attr_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # self._attr_is_on = self.coordinator.data[self.idx]["state"]
        # self.async_write_ha_state()
        self._result = self._hass.data[DOMAIN][self._entry_id].get_result()
        # result = await hass.async_add_executor_job(hub.update)
        self._attr_native_value = self._get_key_result()

        # super()._handle_coordinator_update()
        self._attr_available = True
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Poll battery stack."""
        await self.coordinator.async_request_refresh()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        # self._sensor.enabled = True

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # self._sensor.enabled = False
