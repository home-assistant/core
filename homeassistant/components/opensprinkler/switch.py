"""Opensprinkler integration."""
import logging
from typing import Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from . import OpensprinklerBinarySensor, OpensprinklerCoordinator
from .const import CONF_RUN_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: dict, async_add_entities: Callable,
):
    """Set up the opensprinkler switches."""
    entities = _create_entities(hass, config)
    async_add_entities(entities)


def _create_entities(hass: HomeAssistant, config: dict):
    entities = []

    device = hass.data[DOMAIN][config.entry_id]
    name = config.data[CONF_NAME]
    coordinator = OpensprinklerCoordinator(hass, device)
    entities.append(DeviceSwitch(config.entry_id, name, device, coordinator))

    for program in device.programs:
        entities.append(ProgramSwitch(config.entry_id, program, device, coordinator))

    default_seconds = config.data[CONF_RUN_SECONDS]
    for station in device.stations:
        entities.append(
            StationSwitch(
                config.entry_id, station, device, coordinator, default_seconds
            )
        )

    return entities


class DeviceSwitch(OpensprinklerBinarySensor, SwitchEntity):
    """Represent a switch that reflects whether device is enabled."""

    def __init__(self, entry_id, name, device, coordinator):
        """Set up a new opensprinkler device switch."""
        self._entry_id = entry_id
        self._name = name
        self._device = device
        self._entity_type = "switch"
        super().__init__(coordinator)

    @property
    def name(self) -> str:
        """Return the name of this switch including the device name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_{self.name}"

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._device.device.operation_enabled)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable device operation."""
        await self.hass.async_add_executor_job(self._device.device.disable)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable device operation."""
        await self.hass.async_add_executor_job(self._device.device.enable)


class ProgramSwitch(OpensprinklerBinarySensor, SwitchEntity):
    """Represent a switch that reflects whether program is enabled."""

    def __init__(self, entry_id, program, device, coordinator):
        """Set up a new opensprinkler program switch."""
        self._entry_id = entry_id
        self._program = program
        self._device = device
        self._entity_type = "switch"
        super().__init__(coordinator)

    @property
    def name(self) -> str:
        """Return the name of this switch."""
        return self._program.name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_program_{self.name}"

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._program.enabled)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable program."""
        await self.hass.async_add_executor_job(self._program.disable)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable program."""
        await self.hass.async_add_executor_job(self._program.enable)


class StationSwitch(OpensprinklerBinarySensor, SwitchEntity):
    """Represent a switch that reflects whether station is running."""

    def __init__(self, entry_id, station, device, coordinator, default_seconds):
        """Set up a new opensprinkler station switch."""
        self._entry_id = entry_id
        self._station = station
        self._device = device
        self._default_seconds = default_seconds
        self._entity_type = "switch"
        super().__init__(coordinator)

    @property
    def name(self) -> str:
        """Return the name of this switch."""
        return self._station.name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_station_{self.name}"

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._station.is_running)

    async def async_turn_off(self, **kwargs) -> None:
        """Stop station."""
        await self.hass.async_add_executor_job(self._station.stop)

    async def async_turn_on(self, **kwargs) -> None:
        """Run station."""
        await self.hass.async_add_executor_job(self._station.run, self._default_seconds)
