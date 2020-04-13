"""Opensprinkler integration."""
import logging
from typing import Callable

from homeassistant.components.binary_sensor import BinarySensorDevice
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
    entities.append(
        DeviceBinarySensor(name, device, None, device.device.getOperationEnabled)
    )
    entities.append(
        DeviceBinarySensor(
            f"{name} Rain Delay", device, None, device.device.getRainDelay
        )
    )

    fwv = device.device.getFirmwareVersion()
    hwv = device.device.getHardwareVersion()
    if fwv >= 219:
        entities.append(
            DeviceBinarySensor(
                f"{name} Rain Sensor 1",
                device,
                "moisture",
                device.device.getRainSensor1,
            )
        )
        if hwv / 30 >= 1:
            entities.append(
                DeviceBinarySensor(
                    f"{name} Rain Sensor 2",
                    device,
                    "moisture",
                    device.device.getRainSensor2,
                )
            )
    else:
        entities.append(
            DeviceBinarySensor(
                f"{name} Rain Sensor",
                device,
                "moisture",
                device.device.getRainSensorLegacy,
            )
        )

    for program in device.getPrograms():
        entities.append(ProgramBinarySensor(program, device))

    for station in device.getStations():
        entities.append(StationBinarySensor(station, device))

    return entities


class DeviceBinarySensor(OpensprinklerBinarySensor, BinarySensorDevice):
    """Represent a binary sensor that reflects whether device is enabled."""

    def __init__(self, name, device, sensor_type, state_fn):
        """Set up a new opensprinkler device binary sensor."""
        self._name = name
        self._device = device
        self._sensor_type = sensor_type
        self._state_fn = state_fn
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
        return bool(self._state_fn())


class ProgramBinarySensor(OpensprinklerBinarySensor, BinarySensorDevice):
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
        return bool(self._program.getEnabled())


class StationBinarySensor(OpensprinklerBinarySensor, BinarySensorDevice):
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
        return bool(self._station.getIsRunning())
