"""Asuswrt status sensors."""
from __future__ import annotations

import logging
from numbers import Number

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES, DATA_RATE_MEGABITS_PER_SECOND
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DATA_ASUSWRT,
    DOMAIN,
    SENSOR_CONNECTED_DEVICE,
    SENSOR_RX_BYTES,
    SENSOR_RX_RATES,
    SENSOR_TX_BYTES,
    SENSOR_TX_RATES,
)
from .router import KEY_COORDINATOR, KEY_SENSORS, AsusWrtRouter

DEFAULT_PREFIX = "Asuswrt"

SENSOR_DEVICE_CLASS = "device_class"
SENSOR_ICON = "icon"
SENSOR_NAME = "name"
SENSOR_UNIT = "unit"
SENSOR_FACTOR = "factor"
SENSOR_DEFAULT_ENABLED = "default_enabled"

UNIT_DEVICES = "Devices"

CONNECTION_SENSORS = {
    SENSOR_CONNECTED_DEVICE: {
        SENSOR_NAME: "Devices Connected",
        SENSOR_UNIT: UNIT_DEVICES,
        SENSOR_FACTOR: 0,
        SENSOR_ICON: "mdi:router-network",
        SENSOR_DEVICE_CLASS: None,
        SENSOR_DEFAULT_ENABLED: True,
    },
    SENSOR_RX_RATES: {
        SENSOR_NAME: "Download Speed",
        SENSOR_UNIT: DATA_RATE_MEGABITS_PER_SECOND,
        SENSOR_FACTOR: 125000,
        SENSOR_ICON: "mdi:download-network",
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_TX_RATES: {
        SENSOR_NAME: "Upload Speed",
        SENSOR_UNIT: DATA_RATE_MEGABITS_PER_SECOND,
        SENSOR_FACTOR: 125000,
        SENSOR_ICON: "mdi:upload-network",
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_RX_BYTES: {
        SENSOR_NAME: "Download",
        SENSOR_UNIT: DATA_GIGABYTES,
        SENSOR_FACTOR: 1000000000,
        SENSOR_ICON: "mdi:download",
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_TX_BYTES: {
        SENSOR_NAME: "Upload",
        SENSOR_UNIT: DATA_GIGABYTES,
        SENSOR_FACTOR: 1000000000,
        SENSOR_ICON: "mdi:upload",
        SENSOR_DEVICE_CLASS: None,
    },
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""
    router: AsusWrtRouter = hass.data[DOMAIN][entry.entry_id][DATA_ASUSWRT]
    entities = []

    for sensor_data in router.sensors_coordinator.values():
        coordinator = sensor_data[KEY_COORDINATOR]
        sensors = sensor_data[KEY_SENSORS]
        for sensor_key in sensors:
            if sensor_key in CONNECTION_SENSORS:
                entities.append(
                    AsusWrtSensor(
                        coordinator, router, sensor_key, CONNECTION_SENSORS[sensor_key]
                    )
                )

    async_add_entities(entities, True)


class AsusWrtSensor(CoordinatorEntity, SensorEntity):
    """Representation of a AsusWrt sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: AsusWrtRouter,
        sensor_type: str,
        sensor: dict[str, any],
    ) -> None:
        """Initialize a AsusWrt sensor."""
        super().__init__(coordinator)
        self._router = router
        self._sensor_type = sensor_type
        self._name = f"{DEFAULT_PREFIX} {sensor[SENSOR_NAME]}"
        self._unique_id = f"{DOMAIN} {self._name}"
        self._unit = sensor[SENSOR_UNIT]
        self._factor = sensor[SENSOR_FACTOR]
        self._icon = sensor[SENSOR_ICON]
        self._device_class = sensor[SENSOR_DEVICE_CLASS]
        self._default_enabled = sensor.get(SENSOR_DEFAULT_ENABLED, False)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._default_enabled

    @property
    def state(self) -> str:
        """Return current state."""
        state = self.coordinator.data.get(self._sensor_type)
        if state is None:
            return None
        if self._factor and isinstance(state, Number):
            return round(state / self._factor, 2)
        return state

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit."""
        return self._unit

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Return the device_class."""
        return self._device_class

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return the attributes."""
        return {"hostname": self._router.host}

    @property
    def device_info(self) -> dict[str, any]:
        """Return the device information."""
        return self._router.device_info
