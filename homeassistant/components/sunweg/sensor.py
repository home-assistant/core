"""Read status of SunWEG inverters."""
from __future__ import annotations

import datetime
import logging

from sunweg.api import APIHelper
from sunweg.plant import Plant

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SunWEGData
from .const import CONF_PLANT_ID, DEFAULT_PLANT_ID, DOMAIN
from .sensor_types.inverter import INVERTER_SENSOR_TYPES
from .sensor_types.phase import PHASE_SENSOR_TYPES
from .sensor_types.sensor_entity_description import SunWEGSensorEntityDescription
from .sensor_types.string import STRING_SENSOR_TYPES
from .sensor_types.total import TOTAL_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


def get_device_list(api: APIHelper, config):
    """Retrieve the device list for the selected plant."""
    plant_id = config[CONF_PLANT_ID]

    if plant_id == DEFAULT_PLANT_ID:
        plant_info: list[Plant] = api.listPlants()
        plant_id = plant_info[0].id

    # Get a list of devices for specified plant to add sensors for.
    devices = api.plant(plant_id).inverters
    return [devices, plant_id]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SunWEG sensor."""
    config = {**config_entry.data}
    name = config[CONF_NAME]

    probe: SunWEGData = hass.data[DOMAIN][config_entry.entry_id]

    devices, plant_id = await hass.async_add_executor_job(
        get_device_list, probe.api, config
    )

    entities = [
        SunWEGInverter(
            probe,
            name=f"{name} Total",
            unique_id=f"{plant_id}-{description.key}",
            description=description,
            device_type="total",
        )
        for description in TOTAL_SENSOR_TYPES
    ]

    # Add sensors for each device in the specified plant.
    for device in devices:
        entities.extend(
            [
                SunWEGInverter(
                    probe,
                    name=f"{device.name}",
                    unique_id=f"{device.sn}-{description.key}",
                    description=description,
                    device_type="inverter",
                    inverter_id=device.id,
                )
                for description in INVERTER_SENSOR_TYPES
            ]
        )

        for phase in device.phases:
            entities.extend(
                [
                    SunWEGInverter(
                        probe,
                        name=f"{device.name} {phase.name}",
                        unique_id=f"{device.sn}-{phase.name}-{description.key}",
                        description=description,
                        inverter_id=device.id,
                        device_type="phase",
                        deep_name=phase.name,
                    )
                    for description in PHASE_SENSOR_TYPES
                ]
            )

        for mppt in device.mppts:
            for string in mppt.strings:
                entities.extend(
                    [
                        SunWEGInverter(
                            probe,
                            name=f"{device.name} {string.name}",
                            unique_id=f"{device.sn}-{string.name}-{description.key}",
                            description=description,
                            inverter_id=device.id,
                            device_type="string",
                            deep_name=string.name,
                        )
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
        device_type: str,
        inverter_id: int = 0,
        deep_name: str | None = None,
    ) -> None:
        """Initialize a PVOutput sensor."""
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

    @property
    def native_value(
        self,
    ) -> str | int | float | None | datetime.datetime:
        """Return the state of the sensor."""
        result = self.probe.get_data(
            self.entity_description,
            device_type=self.device_type,
            inverter_id=self.inverter_id,
            deep_name=self.deep_name,
        )
        if self.entity_description.precision is not None:
            result = round(result, self.entity_description.precision)
        return result

    def update(self) -> None:
        """Get the latest data from the Sun WEG API and updates the state."""
        self.probe.update()
