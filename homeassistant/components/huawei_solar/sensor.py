"""Support for Huawei inverter monitoring API."""
import logging

import async_timeout
from huawei_solar import (
    AsyncHuaweiSolar,
    HuaweiSolarException,
    register_names as rn,
    register_values as rv,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    BATTERY_UPDATE_INTERVAL,
    DATA_DEVICE_INFO,
    DATA_MODBUS_CLIENT,
    DOMAIN,
    INVERTER_UPDATE_INTERVAL,
    METER_UPDATE_INTERVAL,
)
from .entity_descriptions import (
    BATTERY_SENSOR_DESCRIPTIONS,
    INVERTER_SENSOR_DESCRIPTIONS,
    OPTIMIZER_SENSOR_DESCRIPTIONS,
    SINGLE_PHASE_METER_SENSOR_DESCRIPTIONS,
    THREE_PHASE_METER_SENSOR_DESCRIPTIONS,
    HuaweiSolarSensorEntityDescription,
    get_pv_entity_descriptions,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities):
    """Add Huawei Solar entry."""
    inverter = hass.data[DOMAIN][entry.entry_id][
        DATA_MODBUS_CLIENT
    ]  # type: AsyncHuaweiSolar
    device_info = hass.data[DOMAIN][entry.entry_id][DATA_DEVICE_INFO]
    inverter_device_id = next(iter(device_info["identifiers"]))

    async def _create_batched_entities(
        entity_descriptions, device_info, coordinator_name, update_interval
    ):
        entity_registers = [descr.key for descr in entity_descriptions]

        async def async_update_data():
            try:
                async with async_timeout.timeout(10):
                    return dict(
                        zip(
                            entity_registers,
                            await inverter.get_multiple(entity_registers),
                        )
                    )
            except HuaweiSolarException as err:
                raise UpdateFailed(
                    f"Could not update {coordinator_name} values: {err}"
                ) from err

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{coordinator_name}_sensors",
            update_method=async_update_data,
            update_interval=update_interval,
        )

        await coordinator.async_config_entry_first_refresh()

        return [
            BatchedHuaweiSolarSensor(coordinator, descr, device_info)
            for descr in entity_descriptions
        ]

    entities_to_add = []

    entities_to_add.extend(
        await _create_batched_entities(
            INVERTER_SENSOR_DESCRIPTIONS,
            device_info,
            "inverter",
            INVERTER_UPDATE_INTERVAL,
        )
    )

    pv_string_count = (await inverter.get(rn.NB_PV_STRINGS)).value
    pv_string_entity_descriptions = []

    for idx in range(1, pv_string_count + 1):
        pv_string_entity_descriptions.extend(get_pv_entity_descriptions(idx))
    entities_to_add.extend(
        await _create_batched_entities(
            pv_string_entity_descriptions,
            device_info,
            "pv_strings",
            INVERTER_UPDATE_INTERVAL,
        )
    )

    # Add power meter sensors if a power meter is detected
    has_power_meter = (
        await inverter.get(rn.METER_STATUS)
    ).value == rv.MeterStatus.NORMAL

    if has_power_meter:

        power_meter_type = (await inverter.get(rn.METER_TYPE)).value

        meter_entity_descriptions = (
            THREE_PHASE_METER_SENSOR_DESCRIPTIONS
            if power_meter_type == rv.MeterType.THREE_PHASE
            else SINGLE_PHASE_METER_SENSOR_DESCRIPTIONS
        )

        power_meter_device_info = {
            "identifiers": {(*device_info, "power_meter")},
            "name": "Power Meter",
            "serial_number": f"{device_info['serial_number']}_PM",
            "via_device": inverter_device_id,
        }

        entities_to_add.extend(
            await _create_batched_entities(
                meter_entity_descriptions,
                power_meter_device_info,
                "meter",
                METER_UPDATE_INTERVAL,
            )
        )

    # Add battery sensors if a battery is detected
    has_battery = inverter.batttery_type != rv.StorageProductModel.NONE

    if has_battery:
        battery_device_info = {
            "identifiers": {(*device_info, "connected_energy_storage")},
            "name": f"{device_info['name']} Connected Energy Storage",
            "serial_number": f"{device_info['serial_number']}_ES",
            "manufacturer": device_info["manufacturer"],
            "model": f"{device_info['model']} Connected Energy Storage",
            "via_device": inverter_device_id,
        }

        entities_to_add.extend(
            await _create_batched_entities(
                BATTERY_SENSOR_DESCRIPTIONS,
                battery_device_info,
                "battery",
                BATTERY_UPDATE_INTERVAL,
            )
        )

    # Add optimizer sensors if optimizers are detected

    has_optimizers = (await inverter.get(rn.NB_OPTIMIZERS)).value

    if has_optimizers:
        entities_to_add.extend(
            [
                HuaweiSolarSensor(inverter, descr, device_info)
                for descr in OPTIMIZER_SENSOR_DESCRIPTIONS
            ]
        )

    async_add_entities(entities_to_add, True)


class HuaweiSolarSensor(SensorEntity):
    """Huawei Solar Sensor."""

    entity_description: HuaweiSolarSensorEntityDescription

    def __init__(
        self,
        inverter: AsyncHuaweiSolar,
        description: HuaweiSolarSensorEntityDescription,
        device_info,
    ):
        """Huawei Solar Sensor Entity constructor."""

        self._inverter = inverter
        self.entity_description = description

        self._attr_device_info = device_info
        self._attr_unique_id = f"{device_info['serial_number']}_{description.key}"

        self._attr_native_value = None

    async def async_update(self):
        """Get the latest data from the Huawei solar inverter."""
        self._attr_native_value = (
            await self._inverter.get(self.entity_description.key)
        ).value


class BatchedHuaweiSolarSensor(CoordinatorEntity, SensorEntity):
    """Huawei Solar Sensor which receives its data via an DataUpdateCoordinator."""

    entity_description: HuaweiSolarSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: HuaweiSolarSensorEntityDescription,
        device_info,
    ):
        """Batched Huawei Solar Sensor Entity constructor."""
        self.coordinator = coordinator
        self.entity_description = description

        self._attr_device_info = device_info
        self._attr_unique_id = f"{device_info['serial_number']}_{description.key}"

    @property
    def native_value(self):
        """Native sensor value."""
        return self.coordinator.data[self.entity_description.key].value
