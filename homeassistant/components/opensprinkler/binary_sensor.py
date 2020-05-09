"""Opensprinkler integration."""
import logging
from typing import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from . import OpensprinklerBinarySensor, OpensprinklerCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: dict, async_add_entities: Callable,
):
    """Set up the opensprinkler binary sensors."""

    entities = await _async_create_entities(hass, config)
    async_add_entities(entities)


async def _async_create_entities(hass: HomeAssistant, config: dict):

    entities = []

    device = hass.data[DOMAIN][config.entry_id]
    name = config.data[CONF_NAME]
    coordinator = OpensprinklerCoordinator(hass, device)
    entities.append(
        DeviceBinarySensor(
            config.entry_id, name, device, coordinator, None, "operation_enabled"
        )
    )
    entities.append(
        DeviceBinarySensor(
            config.entry_id,
            f"{name} Rain Delay",
            device,
            coordinator,
            None,
            "rain_delay",
        )
    )

    fwv = device.device.firmware_version
    hwv = device.device.hardware_version
    if fwv >= 219:
        entities.append(
            DeviceBinarySensor(
                config.entry_id,
                f"{name} Rain Sensor 1",
                device,
                coordinator,
                "moisture",
                "rain_sensor_1",
            )
        )
        if hwv >= 30:
            entities.append(
                DeviceBinarySensor(
                    config.entry_id,
                    f"{name} Rain Sensor 2",
                    device,
                    coordinator,
                    "moisture",
                    "rain_sensor_2",
                )
            )
    else:
        entities.append(
            DeviceBinarySensor(
                config.entry_id,
                f"{name} Rain Sensor",
                device,
                coordinator,
                "moisture",
                "rain_sensor_legacy",
            )
        )

    for program in device.programs:
        entities.append(
            ProgramBinarySensor(config.entry_id, program, device, coordinator)
        )

    for station in device.stations:
        entities.append(
            StationBinarySensor(config.entry_id, station, device, coordinator)
        )

    return entities


class DeviceBinarySensor(OpensprinklerBinarySensor, BinarySensorEntity):
    """Represent a binary sensor that reflects whether device is enabled."""

    def __init__(
        self, entry_id, name, device, coordinator, sensor_type, device_property
    ):
        """Set up a new opensprinkler device binary sensor."""
        self._entry_id = entry_id
        self._name = name
        self._device = device
        self._sensor_type = sensor_type
        self._property = device_property
        self._entity_type = "binary_sensor"
        super().__init__(coordinator)

    @property
    def device_class(self) -> str:
        """Return device type."""
        return self._sensor_type

    @property
    def name(self) -> str:
        """Return the name of this sensor including the device name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_{self._name}"

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(getattr(self._device.device, self._property))


class ProgramBinarySensor(OpensprinklerBinarySensor, BinarySensorEntity):
    """Represent a binary sensor that reflects whether program is enabled."""

    def __init__(self, entry_id, program, device, coordinator):
        """Set up a new opensprinkler device binary sensor."""
        self._entry_id = entry_id
        self._program = program
        self._device = device
        self._entity_type = "binary_sensor"
        super().__init__(coordinator)

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return self._program.name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_program_{self._program.name}"

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._program.enabled)


class StationBinarySensor(OpensprinklerBinarySensor, BinarySensorEntity):
    """Represent a binary sensor that reflects whether station is running."""

    def __init__(self, entry_id, station, device, coordinator):
        """Set up a new opensprinkler device binary sensor."""
        self._entry_id = entry_id
        self._station = station
        self._device = device
        self._entity_type = "binary_sensor"
        super().__init__(coordinator)

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return self._station.name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_station_{self._station.name}"

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return bool(self._station.is_running)
