"""Read status of SunWEG inverters."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from sunweg.api import APIHelper
from sunweg.device import Inverter
from sunweg.plant import Plant

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SunWEGData
from .const import CONF_PLANT_ID, DEFAULT_PLANT_ID, DOMAIN, DeviceType
from .sensor_types.inverter import INVERTER_SENSOR_TYPES
from .sensor_types.phase import PHASE_SENSOR_TYPES
from .sensor_types.sensor_entity_description import SunWEGSensorEntityDescription
from .sensor_types.string import STRING_SENSOR_TYPES
from .sensor_types.total import TOTAL_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


def get_device_list(
    api: APIHelper, config: MappingProxyType[str, Any]
) -> tuple[list[Inverter], int]:
    """Retrieve the device list for the selected plant."""
    plant_id = int(config[CONF_PLANT_ID])

    if plant_id == DEFAULT_PLANT_ID:
        plant_info: list[Plant] = api.listPlants()
        plant_id = plant_info[0].id

    devices: list[Inverter] = []
    # Get a list of devices for specified plant to add sensors for.
    for inverter in api.plant(plant_id).inverters:
        api.complete_inverter(inverter)
        devices.append(inverter)
    return (devices, plant_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SunWEG sensor."""
    name = config_entry.data[CONF_NAME]

    probe: SunWEGData = hass.data[DOMAIN][config_entry.entry_id]

    devices, plant_id = await hass.async_add_executor_job(
        get_device_list, probe.api, config_entry.data
    )

    entities = [
        SunWEGInverter(
            probe,
            name=f"{name} Total",
            unique_id=f"{plant_id}-{description.key}",
            description=description,
            device_type=DeviceType.TOTAL,
        )
        for description in TOTAL_SENSOR_TYPES
    ]

    # Add sensors for each device in the specified plant.
    entities.extend(
        [
            SunWEGInverter(
                probe,
                name=f"{device.name}",
                unique_id=f"{device.sn}-{description.key}",
                description=description,
                device_type=DeviceType.INVERTER,
                inverter_id=device.id,
            )
            for device in devices
            for description in INVERTER_SENSOR_TYPES
        ]
    )

    entities.extend(
        [
            SunWEGInverter(
                probe,
                name=f"{device.name} {phase.name}",
                unique_id=f"{device.sn}-{phase.name}-{description.key}",
                description=description,
                inverter_id=device.id,
                device_type=DeviceType.PHASE,
                deep_name=phase.name,
            )
            for device in devices
            for phase in device.phases
            for description in PHASE_SENSOR_TYPES
        ]
    )

    entities.extend(
        [
            SunWEGInverter(
                probe,
                name=f"{device.name} {string.name}",
                unique_id=f"{device.sn}-{string.name}-{description.key}",
                description=description,
                inverter_id=device.id,
                device_type=DeviceType.STRING,
                deep_name=string.name,
            )
            for device in devices
            for mppt in device.mppts
            for string in mppt.strings
            for description in STRING_SENSOR_TYPES
        ]
    )

    async_add_entities(entities, True)


class SunWEGInverter(SensorEntity):
    """Representation of a SunWEG Sensor."""

    entity_description: SunWEGSensorEntityDescription

    def __init__(
        self,
        probe: SunWEGData,
        name: str,
        unique_id: str,
        description: SunWEGSensorEntityDescription,
        device_type: DeviceType,
        inverter_id: int = 0,
        deep_name: str | None = None,
    ) -> None:
        """Initialize a sensor."""
        self.probe = probe
        self.entity_description = description
        self.device_type = device_type
        self.inverter_id = inverter_id
        self.deep_name = deep_name

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = unique_id
        self._attr_icon = (
            description.icon if description.icon is not None else "mdi:solar-power"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(probe.plant_id))},
            manufacturer="SunWEG",
            name=name,
        )

    def update(self) -> None:
        """Get the latest data from the Sun WEG API and updates the state."""
        self.probe.update()
        (
            self._attr_native_value,
            self._attr_native_unit_of_measurement,
        ) = self.probe.get_data(
            api_variable_key=self.entity_description.api_variable_key,
            api_variable_unit=self.entity_description.api_variable_unit,
            deep_name=self.deep_name,
            device_type=self.device_type,
            inverter_id=self.inverter_id,
            name=self.entity_description.name,
            native_unit_of_measurement=self.native_unit_of_measurement,
            never_resets=self.entity_description.never_resets,
            previous_value_drop_threshold=self.entity_description.previous_value_drop_threshold,
        )
