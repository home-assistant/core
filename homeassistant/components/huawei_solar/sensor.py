"""Support for Huawei inverter monitoring API."""
from __future__ import annotations

import logging

from huawei_solar import AsyncHuaweiSolar, register_names as rn

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import (
    HuaweiInverterSlaveDeviceInfos,
    HuaweiSolarRegisterUpdateCoordinator,
    get_device_info_unique_id,
)
from .const import (
    DATA_DEVICE_INFOS,
    DATA_MODBUS_CLIENT,
    DATA_UPDATE_COORDINATORS,
    DOMAIN,
)
from .entity_descriptions import HuaweiSolarSensorEntityDescription

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
    slave_device_infos = hass.data[DOMAIN][entry.entry_id][
        DATA_DEVICE_INFOS
    ]  # type: list[HuaweiInverterSlaveDeviceInfos]
    update_coordinators = hass.data[DOMAIN][entry.entry_id][
        DATA_UPDATE_COORDINATORS
    ]  # type: list[HuaweiSolarRegisterUpdateCoordinator]

    # Create all sensor-entities that are available via the created update coordinators.
    entities_to_add: list[SensorEntity] = []
    for update_coordinator in update_coordinators:
        for entity_description in update_coordinator.entity_descriptions:

            if isinstance(entity_description, HuaweiSolarSensorEntityDescription):
                entities_to_add.append(
                    BatchedHuaweiSolarSensor(
                        update_coordinator,
                        entity_description,
                        update_coordinator.device_info,
                    )
                )

    # Add optimizer sensors if optimizers are detected
    for slave_device_info in slave_device_infos:
        inverter_device_info = slave_device_info["inverter"]
        slave_id = slave_device_info["slave_id"]
        has_optimizers = (await inverter.get(rn.NB_OPTIMIZERS, slave_id)).value

        if has_optimizers:
            entities_to_add.extend(
                [
                    HuaweiSolarSensor(inverter, slave_id, descr, inverter_device_info)
                    for descr in OPTIMIZER_SENSOR_DESCRIPTIONS
                ]
            )

    async_add_entities(entities_to_add, True)


OPTIMIZER_SENSOR_DESCRIPTIONS = [
    HuaweiSolarSensorEntityDescription(
        key=rn.NB_ONLINE_OPTIMIZERS,
        name="Optimizers Online",
        icon="mdi:solar-panel",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


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
        self._attr_unique_id = (
            f"{get_device_info_unique_id(device_info)}_{description.key}"
        )

        self._attr_native_value = None

    async def async_update(self):
        """Get the latest data from the Huawei solar inverter."""
        self._attr_native_value = (
            await self._inverter.get(self.entity_description.key, self._slave)
        ).value


class BatchedHuaweiSolarSensor(CoordinatorEntity, SensorEntity):
    """Huawei Solar Sensor which receives its data via an DataUpdateCoordinator."""

    entity_description: HuaweiSolarSensorEntityDescription

    def __init__(
        self,
        coordinator: HuaweiSolarRegisterUpdateCoordinator,
        description: HuaweiSolarSensorEntityDescription,
        device_info,
    ):
        """Batched Huawei Solar Sensor Entity constructor."""
        super().__init__(coordinator)

        self.coordinator = coordinator
        self.entity_description = description

        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{get_device_info_unique_id(device_info)}_{description.key}"
        )

    @property
    def native_value(self):
        """Native sensor value."""
        return self.coordinator.data[self.entity_description.key].value
