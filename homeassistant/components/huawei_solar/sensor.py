"""Support for Huawei inverter monitoring API."""
from __future__ import annotations

from dataclasses import dataclass
import logging

import async_timeout
from huawei_solar import (
    AsyncHuaweiSolar,
    HuaweiSolarException,
    register_names as rn,
    register_values as rv,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_VOLT_AMPERE_REACTIVE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    BATTERY_UPDATE_INTERVAL,
    DATA_DEVICE_INFO,
    DATA_EXTRA_SLAVE_IDS,
    DATA_MODBUS_CLIENT,
    DOMAIN,
    INVERTER_UPDATE_INTERVAL,
    METER_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Huawei Solar entry."""
    inverter = hass.data[DOMAIN][entry.entry_id][
        DATA_MODBUS_CLIENT
    ]  # type: AsyncHuaweiSolar
    device_info = hass.data[DOMAIN][entry.entry_id][DATA_DEVICE_INFO]
    inverter_device_id = next(iter(device_info["identifiers"]))

    entities_to_add = []

    # Always add the entities of the inverter we are connecting to with slave=None

    entities_to_add.extend(await _compute_slave_entities(hass, inverter, None, None))
    for slave_id in hass.data[DOMAIN][entry.entry_id][DATA_EXTRA_SLAVE_IDS]:
        entities_to_add.extend(
            await _compute_slave_entities(hass, inverter, slave_id, inverter_device_id)
        )

    async_add_entities(entities_to_add, True)


async def _compute_slave_entities(
    hass,
    inverter: AsyncHuaweiSolar,
    slave: int | None,
    connecting_inverter_device_id: tuple | None,
):
    """Add all relevant entities for a certain slave.

    If slave is None, then the default slave configured in the AsyncHuaweiSolar-object will be used.
    This is typically the inverter to which we make the Modbus-TCP connection.
    """

    entities_to_add = []

    model_name, serial_number = await inverter.get_multiple(
        [rn.MODEL_NAME, rn.SERIAL_NUMBER]
    )

    current_inverter_identifier_list = [DOMAIN, model_name.value, serial_number.value]

    if slave is not None:
        current_inverter_identifier_list.append(slave)

    current_inverter_identifier = tuple(current_inverter_identifier_list)

    device_info = {
        "identifiers": {current_inverter_identifier},
        "name": model_name.value,
        "manufacturer": "Huawei",
        "serial_number": serial_number.value,
        "model": model_name.value,
    }
    if connecting_inverter_device_id:
        device_info["via"] = connecting_inverter_device_id

    entities_to_add.extend(
        await _create_batched_entities(
            hass,
            inverter,
            slave,
            INVERTER_SENSOR_DESCRIPTIONS,
            device_info,
            "inverter",
            INVERTER_UPDATE_INTERVAL,
        )
    )

    pv_string_count = (await inverter.get(rn.NB_PV_STRINGS, slave)).value
    pv_string_entity_descriptions = []

    for idx in range(1, pv_string_count + 1):
        pv_string_entity_descriptions.extend(get_pv_entity_descriptions(idx))
    entities_to_add.extend(
        await _create_batched_entities(
            hass,
            inverter,
            slave,
            pv_string_entity_descriptions,
            device_info,
            "pv_strings",
            INVERTER_UPDATE_INTERVAL,
        )
    )

    # Add power meter sensors if a power meter is detected
    has_power_meter = (
        await inverter.get(rn.METER_STATUS, slave)
    ).value == rv.MeterStatus.NORMAL

    if has_power_meter:

        power_meter_type = (await inverter.get(rn.METER_TYPE, slave)).value

        meter_entity_descriptions = (
            THREE_PHASE_METER_SENSOR_DESCRIPTIONS
            if power_meter_type == rv.MeterType.THREE_PHASE
            else SINGLE_PHASE_METER_SENSOR_DESCRIPTIONS
        )

        power_meter_device_info = {
            "identifiers": {(*device_info, "power_meter")},
            "name": "Power Meter",
            "serial_number": f"{device_info['serial_number']}_PM",
            "via_device": current_inverter_identifier,
        }

        entities_to_add.extend(
            await _create_batched_entities(
                hass,
                inverter,
                slave,
                meter_entity_descriptions,
                power_meter_device_info,
                "meter",
                METER_UPDATE_INTERVAL,
            )
        )

    # Add battery sensors if a battery is detected
    has_battery = inverter.battery_type != rv.StorageProductModel.NONE

    if has_battery:
        battery_device_info = {
            "identifiers": {(*device_info, "connected_energy_storage")},
            "name": f"{device_info['name']} Connected Energy Storage",
            "serial_number": f"{device_info['serial_number']}_ES",
            "manufacturer": device_info["manufacturer"],
            "model": f"{device_info['model']} Connected Energy Storage",
            "via_device": current_inverter_identifier,
        }

        entities_to_add.extend(
            await _create_batched_entities(
                hass,
                inverter,
                slave,
                BATTERY_SENSOR_DESCRIPTIONS,
                battery_device_info,
                "battery",
                BATTERY_UPDATE_INTERVAL,
            )
        )

    # Add optimizer sensors if optimizers are detected

    has_optimizers = (await inverter.get(rn.NB_OPTIMIZERS, slave)).value

    if has_optimizers:
        entities_to_add.extend(
            [
                HuaweiSolarSensor(inverter, slave, descr, device_info)
                for descr in OPTIMIZER_SENSOR_DESCRIPTIONS
            ]
        )

    return entities_to_add


@dataclass
class HuaweiSolarSensorEntityDescription(SensorEntityDescription):
    """Huawei Solar Sensor Entity."""


class HuaweiSolarSensor(SensorEntity):
    """Huawei Solar Sensor."""

    entity_description: HuaweiSolarSensorEntityDescription

    def __init__(
        self,
        inverter: AsyncHuaweiSolar,
        slave: int | None,
        description: HuaweiSolarSensorEntityDescription,
        device_info,
    ):
        """Huawei Solar Sensor Entity constructor."""

        self._inverter = inverter
        self._slave = slave
        self.entity_description = description

        self._attr_device_info = device_info
        self._attr_unique_id = f"{device_info['serial_number']}_{description.key}{f'_slave_{slave}' if slave else ''}"

        self._attr_native_value = None

    async def async_update(self):
        """Get the latest data from the Huawei solar inverter."""
        self._attr_native_value = (
            await self._inverter.get(self.entity_description.key, self._slave)
        ).value


async def _create_batched_entities(
    hass,
    inverter: AsyncHuaweiSolar,
    slave,
    entity_descriptions,
    device_info,
    coordinator_name,
    update_interval,
):
    entity_registers = [descr.key for descr in entity_descriptions]

    async def async_update_data():
        try:
            async with async_timeout.timeout(10):
                return dict(
                    zip(
                        entity_registers,
                        await inverter.get_multiple(entity_registers, slave),
                    )
                )
        except HuaweiSolarException as err:
            raise UpdateFailed(
                f"Could not update {coordinator_name} values: {err}"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{coordinator_name}_sensors{f'_slave_{slave}' if slave else ''}",
        update_method=async_update_data,
        update_interval=update_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    return [
        BatchedHuaweiSolarSensor(coordinator, slave, descr, device_info)
        for descr in entity_descriptions
    ]


class BatchedHuaweiSolarSensor(CoordinatorEntity, SensorEntity):
    """Huawei Solar Sensor which receives its data via an DataUpdateCoordinator."""

    entity_description: HuaweiSolarSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        slave: int | None,
        description: HuaweiSolarSensorEntityDescription,
        device_info,
    ):
        """Batched Huawei Solar Sensor Entity constructor."""
        super().__init__(coordinator)

        self.coordinator = coordinator
        self.entity_description = description

        self._attr_device_info = device_info
        self._attr_unique_id = f"{device_info['serial_number']}_{description.key}{f'_slave_{slave}' if slave else ''}"

    @property
    def native_value(self):
        """Native sensor value."""
        return self.coordinator.data[self.entity_description.key].value


# Every list in this file describes a group of entities which are related to each other.
# The order of these lists matters, as they need to be in ascending order wrt. to their modbus-register.


INVERTER_SENSOR_DESCRIPTIONS: list[HuaweiSolarSensorEntityDescription] = [
    HuaweiSolarSensorEntityDescription(
        key=rn.INPUT_POWER,
        name="Input Power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.DAY_ACTIVE_POWER_PEAK,
        name="Day Active Power Peak",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_POWER,
        name="Active Power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.REACTIVE_POWER,
        name="Reactive Power",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.POWER_FACTOR,
        name="Power Factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.EFFICIENCY,
        name="Efficiency",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.INTERNAL_TEMPERATURE,
        name="Internal Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.DEVICE_STATUS,
        name="Device Status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.STARTUP_TIME,
        name="Startup Time",
        icon="mdi:weather-sunset-up",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.SHUTDOWN_TIME,
        name="Shutdown Time",
        icon="mdi:weather-sunset-down",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACCUMULATED_YIELD_ENERGY,
        name="Total Yield",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.DAILY_YIELD_ENERGY,
        name="Daily Yield",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]


SINGLE_PHASE_METER_SENSOR_DESCRIPTIONS: list[HuaweiSolarSensorEntityDescription] = [
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_A_VOLTAGE,
        name="Grid Voltage",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_A_CURRENT,
        name="Grid Current",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.POWER_METER_ACTIVE_POWER,
        name="Active Power",
        icon="mdi:flash",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.POWER_METER_REACTIVE_POWER,
        name="Reactive Power",
        icon="mdi:flash",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_POWER_FACTOR,
        name="Power Factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_FREQUENCY,
        name="Grid Frequency",
        native_unit_of_measurement="Hz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_EXPORTED_ENERGY,
        name="Grid Exported",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_ACCUMULATED_ENERGY,
        name="Grid Consumption",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_ACCUMULATED_REACTIVE_POWER,
        name="Grid Reactive Power",
        native_unit_of_measurement="kVarh",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_A_POWER,
        name="Grid Active Power",
        icon="mdi:flash",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


THREE_PHASE_METER_SENSOR_DESCRIPTIONS: list[HuaweiSolarSensorEntityDescription] = [
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_A_VOLTAGE,
        name="Grid A phase voltage",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_B_VOLTAGE,
        name="Grid B phase voltage",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_C_VOLTAGE,
        name="Grid C phase voltage",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_A_CURRENT,
        name="Grid A phase current",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_B_CURRENT,
        name="Grid B phase current",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_C_CURRENT,
        name="Grid C phase current",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.POWER_METER_ACTIVE_POWER,
        name="Active Power",
        icon="mdi:flash",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.POWER_METER_REACTIVE_POWER,
        name="Reactive Power",
        icon="mdi:flash",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_POWER_FACTOR,
        name="Power Factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_FREQUENCY,
        name="Grid Frequency",
        native_unit_of_measurement="Hz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_EXPORTED_ENERGY,
        name="Grid Exported",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_ACCUMULATED_ENERGY,
        name="Grid Consumption",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.GRID_ACCUMULATED_REACTIVE_POWER,
        name="Grid Reactive Power",
        native_unit_of_measurement="kVarh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_A_B_VOLTAGE,
        name="A-B line voltage",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_B_C_VOLTAGE,
        name="B-C line voltage",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_C_A_VOLTAGE,
        name="C-A line voltage",
        icon="mdi:flash",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_A_POWER,
        name="A phase Active Power",
        icon="mdi:flash",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_B_POWER,
        name="B phase Active Power",
        icon="mdi:flash",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.ACTIVE_GRID_C_POWER,
        name="C phase Active Power",
        icon="mdi:flash",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

BATTERY_SENSOR_DESCRIPTIONS: list[HuaweiSolarSensorEntityDescription] = [
    HuaweiSolarSensorEntityDescription(
        key=rn.STORAGE_STATE_OF_CAPACITY,
        name="Battery State of Capacity",
        icon="mdi:home-battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.STORAGE_BUS_VOLTAGE,
        name="Storage Bus Voltage",
        icon="mdi:home-lightning-bolt",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.STORAGE_BUS_CURRENT,
        name="Storage Bus Current",
        icon="mdi:home-lightning-bolt-outline",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.STORAGE_CHARGE_DISCHARGE_POWER,
        name="Charge/Discharge Power",
        icon="mdi:home-battery-outline",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.STORAGE_TOTAL_CHARGE,
        name="Battery Total Charge",
        icon="mdi:battery-plus-variant",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.STORAGE_TOTAL_DISCHARGE,
        name="Battery Total Discharge",
        icon="mdi:battery-minus-variant",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.STORAGE_CURRENT_DAY_CHARGE_CAPACITY,
        name="Battery Day Charge",
        icon="mdi:battery-plus-variant",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    HuaweiSolarSensorEntityDescription(
        key=rn.STORAGE_CURRENT_DAY_DISCHARGE_CAPACITY,
        name="Battery Day Discharge",
        icon="mdi:battery-minus-variant",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
]


OPTIMIZER_SENSOR_DESCRIPTIONS = [
    HuaweiSolarSensorEntityDescription(
        key=rn.NB_ONLINE_OPTIMIZERS,
        name="Optimizers Online",
        icon="mdi:solar-panel",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


def get_pv_entity_descriptions(idx: int):
    """Create the entity descriptions for a PV string."""
    assert 1 <= idx <= 24

    return [
        HuaweiSolarSensorEntityDescription(
            key=getattr(rn, f"PV_{idx:02}_VOLTAGE"),
            name=f"PV {idx} Voltage",
            icon="mdi:lightning-bolt",
            native_unit_of_measurement=POWER_WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HuaweiSolarSensorEntityDescription(
            key=getattr(rn, f"PV_{idx:02}_CURRENT"),
            name=f"PV {idx} Current",
            icon="mdi:lightning-bolt-outline",
            native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ]
