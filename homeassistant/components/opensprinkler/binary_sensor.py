"""Opensprinkler integration."""
import logging
from typing import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant

from . import OpensprinklerBinarySensor
from .const import DATA_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: Callable,
    discovery_info: dict,
):
    """Set up the opensprinkler binary sensors."""
    entities = await hass.async_add_executor_job(
        _create_entities, hass, config, discovery_info
    )
    async_add_entities(entities)


def _create_entities(hass: HomeAssistant, config: dict, discovery_info: dict):
    entities = []

    name = discovery_info["name"]
    device = hass.data[DOMAIN][DATA_DEVICES][name]
    entities.append(DeviceBinarySensor(name, device, None, "operation_enabled"))
    entities.append(
        DeviceBinarySensor(f"{name} Rain Delay", device, None, "rain_delay")
    )

    fwv = device.device.firmware_version
    hwv = device.device.hardware_version
    if fwv >= 219:
        entities.append(
            DeviceBinarySensor(
                f"{name} Rain Sensor 1", device, "moisture", "rain_sensor_1",
            )
        )
        if hwv >= 30:
            entities.append(
                DeviceBinarySensor(
                    f"{name} Rain Sensor 2", device, "moisture", "rain_sensor_2",
                )
            )
    else:
        entities.append(
            DeviceBinarySensor(
                f"{name} Rain Sensor", device, "moisture", "rain_sensor_legacy",
            )
        )

    for program in device.programs:
        entities.append(ProgramBinarySensor(program, device))

    for station in device.stations:
        entities.append(StationBinarySensor(station, device))

    return entities


class DeviceBinarySensor(OpensprinklerBinarySensor, BinarySensorEntity):
    """Represent a binary sensor that reflects whether device is enabled."""

    def __init__(self, name, device, sensor_type, device_property):
        """Set up a new opensprinkler device binary sensor."""
        self._name = name
        self._device = device
        self._sensor_type = sensor_type
        self._property = device_property
        super().__init__()

    @property
    def device_class(self) -> str:
        """Return device type."""
        return self._sensor_type

    @property
    def name(self) -> str:
        """Return the name of this sensor including the device name."""
        return self._name

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(getattr(self._device.device, self._property))


class ProgramBinarySensor(OpensprinklerBinarySensor, BinarySensorEntity):
    """Represent a binary sensor that reflects whether program is enabled."""

    def __init__(self, program, device):
        """Set up a new opensprinkler device binary sensor."""
        self._program = program
        self._device = device
        super().__init__()

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return self._program.name

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._program.enabled)


class StationBinarySensor(OpensprinklerBinarySensor, BinarySensorEntity):
    """Represent a binary sensor that reflects whether station is running."""

    def __init__(self, station, device):
        """Set up a new opensprinkler device binary sensor."""
        self._station = station
        self._device = device
        super().__init__()

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return self._station.name

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._station.is_running)
