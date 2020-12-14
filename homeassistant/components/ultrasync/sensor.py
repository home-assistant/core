"""Monitor the Interlogix/Hills ComNav UltraSync Hub."""

import logging
from typing import Callable, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import UltraSyncEntity
from .const import (
    DATA_COORDINATOR,
    DATA_UNDO_UPDATE_LISTENER,
    DOMAIN,
    SENSOR_UPDATE_LISTENER,
    SENSORS,
)
from .coordinator import UltraSyncDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up UltraSync sensor based on a config entry."""
    coordinator: UltraSyncDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    # At least one sensor must be pre-created or Home Assistant will not
    # call any updates
    hass.data[DOMAIN][entry.entry_id][SENSORS]["area01_state"] = UltraSyncSensor(
        coordinator, entry.entry_id, entry.data[CONF_NAME], "area01_state", "Area1State"
    )

    async_add_entities([hass.data[DOMAIN][entry.entry_id][SENSORS]["area01_state"]])

    @callback
    def _auto_manage_sensors(areas: dict, zones: dict) -> None:
        """Dynamically create/delete sensors based on what was detected by the hub."""

        _LOGGER.debug(
            "Entering _auto_manage_sensors with %d area(s), and %d zone(s)",
            len(areas),
            len(zones),
        )

        # our list of sensors to add
        new_sensors = []

        # A pointer to our sensors
        sensors = hass.data[DOMAIN][entry.entry_id][SENSORS]

        # Track our detected sensors (for automatic updates if required)
        detected_sensors = set()

        for meta in areas:
            bank_no = meta["bank"]
            sensor_id = "area{:0>2}_state".format(bank_no + 1)
            detected_sensors.add(sensor_id)
            if sensor_id not in sensors:
                # hash our entry
                sensors[sensor_id] = UltraSyncSensor(
                    coordinator,
                    entry.entry_id,
                    entry.data[CONF_NAME],
                    sensor_id,
                    # Friendly Name
                    "Area{}State".format(bank_no + 1),
                )

                # Add our new area sensor
                new_sensors.append(sensors[sensor_id])
                _LOGGER.debug(
                    "Detected %s.Area%dState", entry.data[CONF_NAME], bank_no + 1
                )

            # Update our meta information
            for key, value in meta.items():
                sensors[sensor_id][key] = value

        for meta in zones:
            bank_no = meta["bank"]
            sensor_id = "zone{:0>2}_state".format(bank_no + 1)
            detected_sensors.add(sensor_id)
            if sensor_id not in sensors:
                # hash our entry
                sensors[sensor_id] = UltraSyncSensor(
                    coordinator,
                    entry.entry_id,
                    entry.data[CONF_NAME],
                    sensor_id,
                    # Friendly Name
                    "Zone{}State".format(bank_no + 1),
                )

                # Add our new zone sensor
                new_sensors.append(sensors[sensor_id])
                _LOGGER.debug(
                    "Detected %s.Zone%dState", entry.data[CONF_NAME], bank_no + 1
                )

            # Update our meta information
            for key, value in meta.items():
                sensors[sensor_id][key] = value

        if new_sensors:
            # Add our newly detected sensors
            async_add_entities(new_sensors)

        for sensor_id in set(sensors.keys()).difference(detected_sensors):
            # Tidy up sensors leaving our listing
            hass.async_create_task(sensors[sensor_id].async_remove())
            del sensors[sensor_id]

    # register our callback which will be called the second we make a
    # connection to our panel
    hass.data[DOMAIN][entry.entry_id][DATA_UNDO_UPDATE_LISTENER].append(
        async_dispatcher_connect(hass, SENSOR_UPDATE_LISTENER, _auto_manage_sensors)
    )


class UltraSyncSensor(UltraSyncEntity):
    """Representation of a UltraSync sensor."""

    def __init__(
        self,
        coordinator: UltraSyncDataUpdateCoordinator,
        entry_id: str,
        entry_name: str,
        sensor_type: str,
        sensor_name: str,
    ):
        """Initialize a new UltraSync sensor."""

        self._sensor_type = sensor_type
        self._unique_id = f"{entry_id}_{sensor_type}"

        # Initialize our Attributes
        self.__attributes = {}

        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            name=f"{entry_name} {sensor_name}",
        )

    def __setitem__(self, key, value):
        """Set our sensor attributes."""
        self.__attributes[key] = value

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self.__attributes

    @property
    def state(self):
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self._sensor_type)
        if value is None:
            _LOGGER.warning("Unable to locate value for %s", self._sensor_type)
            return None

        return value
