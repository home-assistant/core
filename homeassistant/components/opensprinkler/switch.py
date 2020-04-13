"""Opensprinkler integration."""
import logging
from typing import Callable

from homeassistant.components.switch import SwitchDevice
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
    """Set up the opensprinkler switches."""
    entities = await hass.async_add_executor_job(
        _create_entities, hass, config, discovery_info
    )
    async_add_entities(entities)


def _create_entities(hass: HomeAssistant, config: dict, discovery_info: dict):
    entities = []

    name = discovery_info["name"]
    device = hass.data[DOMAIN][DATA_DEVICES][name]
    entities.append(DeviceSwitch(name, device))

    for program in device.getPrograms():
        entities.append(ProgramSwitch(program, device))

    default_seconds = discovery_info["default_seconds"]
    for station in device.getStations():
        entities.append(StationSwitch(station, device, default_seconds))

    return entities


class DeviceSwitch(OpensprinklerBinarySensor, SwitchDevice):
    """Represent a switch that reflects whether device is enabled."""

    def __init__(self, name, device):
        """Set up a new opensprinkler device switch."""
        self._name = name
        self._device = device
        super().__init__()

    @property
    def name(self) -> str:
        """Return the name of this switch including the device name."""
        return self._name

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._device.device.getOperationEnabled())

    async def async_turn_off(self, **kwargs) -> None:
        """Disable device operation."""
        self._device.device.disable()

    async def async_turn_on(self, **kwargs) -> None:
        """Enable device operation."""
        self._device.device.enable()


class ProgramSwitch(OpensprinklerBinarySensor, SwitchDevice):
    """Represent a switch that reflects whether program is enabled."""

    def __init__(self, program, device):
        """Set up a new opensprinkler program switch."""
        self._program = program
        self._device = device
        super().__init__()

    @property
    def name(self) -> str:
        """Return the name of this switch."""
        return self._program.name

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._program.getEnabled())

    async def async_turn_off(self, **kwargs) -> None:
        """Disable program."""
        self._program.disable()

    async def async_turn_on(self, **kwargs) -> None:
        """Enable program."""
        self._program.enable()


class StationSwitch(OpensprinklerBinarySensor, SwitchDevice):
    """Represent a switch that reflects whether station is running."""

    def __init__(self, station, device, default_seconds):
        """Set up a new opensprinkler station switch."""
        self._station = station
        self._device = device
        self._default_seconds = default_seconds
        super().__init__()

    @property
    def name(self) -> str:
        """Return the name of this switch."""
        return self._station.name

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._station.getIsRunning())

    async def async_turn_off(self, **kwargs) -> None:
        """Stop station."""
        self._station.stop()

    async def async_turn_on(self, **kwargs) -> None:
        """Run station."""
        self._station.run(self._default_seconds)
