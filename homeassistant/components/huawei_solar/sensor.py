"""Support for Huawei inverter monitoring API."""
from huawei_solar import AsyncHuaweiSolar, register_names as rn, register_values as rv

from homeassistant.components.sensor import SensorEntity

from .const import (
    BATTERY_SENSOR_TYPES,
    DATA_DEVICE_INFO,
    DATA_MODBUS_CLIENT,
    DOMAIN,
    OPTIMIZER_SENSOR_TYPES,
    SENSOR_TYPES,
    HuaweiSolarSensorEntityDescription,
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add Huawei Solar entry."""
    inverter = hass.data[DOMAIN][entry.entry_id][
        DATA_MODBUS_CLIENT
    ]  # type: AsyncHuaweiSolar

    device_info = hass.data[DOMAIN][entry.entry_id][DATA_DEVICE_INFO]

    async_add_entities(
        [HuaweiSolarSensor(inverter, descr, device_info) for descr in SENSOR_TYPES],
        True,
    )

    # Add battery sensors if a battery is detected
    has_battery = inverter.batttery_type != rv.StorageProductModel.NONE

    if has_battery:
        async_add_entities(
            [
                HuaweiSolarSensor(inverter, descr, device_info)
                for descr in BATTERY_SENSOR_TYPES
            ],
            True,
        )

    # Add optimizer sensors if optimizers are detected

    has_optimizers = (await inverter.get(rn.NB_OPTIMIZERS)).value

    if has_optimizers:
        async_add_entities(
            [
                HuaweiSolarSensor(inverter, descr, device_info)
                for descr in OPTIMIZER_SENSOR_TYPES
            ],
            True,
        )


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
