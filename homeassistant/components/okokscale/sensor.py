"""Support for OKOK Scale sensors."""

from typing import override

from okokscale.parser import (
    SensorDeviceClass as OKOKScaleSensorDeviceClass,
    SensorUpdate,
    Units,
)

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from . import OKOKScaleConfigEntry
from .device import device_key_to_bluetooth_entity_key

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

SENSOR_DESCRIPTIONS = {
    (OKOKScaleSensorDeviceClass.MASS, Units.MASS_KILOGRAMS): SensorEntityDescription(
        key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        icon="mdi:scale-bathroom",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    (OKOKScaleSensorDeviceClass.MASS, Units.MASS_POUNDS): SensorEntityDescription(
        key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        icon="mdi:scale-bathroom",
        native_unit_of_measurement=UnitOfMass.POUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    (
        OKOKScaleSensorDeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=OKOKScaleSensorDeviceClass.SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (OKOKScaleSensorDeviceClass.BATTERY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{OKOKScaleSensorDeviceClass.BATTERY}_percent",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (OKOKScaleSensorDeviceClass.IMPEDANCE, Units.OHM): SensorEntityDescription(
        key=OKOKScaleSensorDeviceClass.IMPEDANCE,
        native_unit_of_measurement="Ω",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    entity_descriptions: dict[PassiveBluetoothEntityKey, EntityDescription] = {
        device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
            (description.device_class, description.native_unit_of_measurement)
        ]
        for device_key, description in sensor_update.entity_descriptions.items()
        if description.device_class and description.native_unit_of_measurement
    }

    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions=entity_descriptions,
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
            # Add names where the entity description has neither a translation_key nor
            # a device_class
            if (
                description := entity_descriptions.get(
                    device_key_to_bluetooth_entity_key(device_key)
                )
            )
            is None
            or (
                description.translation_key is None and description.device_class is None
            )
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OKOKScaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OKOK Scale sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            OKOKScaleBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, SensorEntityDescription)
    )


class OKOKScaleBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[str | float | None, SensorUpdate]
    ],
    SensorEntity,
):
    """Representation of an OKOK Scale sensor."""

    @property
    @override
    def native_value(self) -> str | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available.

        The sensor is only created when the device is seen.

        Since these are sleepy devices which stop broadcasting
        when not in use, we can't rely on the last update time
        so once we have seen the device we always return True.
        """
        return True

    @property
    @override
    def assumed_state(self) -> bool:
        """Return True if the device is no longer broadcasting."""
        return not self.processor.available
