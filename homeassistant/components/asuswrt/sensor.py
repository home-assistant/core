"""Asuswrt status sensors."""
import logging
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_GIGABYTES,
    DATA_RATE_MEGABITS_PER_SECOND,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    DOMAIN,
    SENSOR_CONNECTED_DEVICE,
    SENSOR_RX_BYTES,
    SENSOR_RX_RATES,
    SENSOR_TX_BYTES,
    SENSOR_TX_RATES,
)
from .router import AsusWrtRouter

SENSOR_DEVICE_CLASS = "device_class"
SENSOR_ICON = "icon"
SENSOR_NAME = "name"
SENSOR_UNIT = "unit"
SENSOR_FACTOR = "factor"

CONNECTION_SENSORS = {
    SENSOR_CONNECTED_DEVICE: {
        SENSOR_NAME: "AsusWrt connected devices",
        SENSOR_UNIT: None,
        SENSOR_FACTOR: 0,
        SENSOR_ICON: None,
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_RX_RATES: {
        SENSOR_NAME: "AsusWrt download speed",
        SENSOR_UNIT: DATA_RATE_MEGABITS_PER_SECOND,
        SENSOR_FACTOR: 125000,
        SENSOR_ICON: "mdi:download-network",
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_TX_RATES: {
        SENSOR_NAME: "AsusWrt upload speed",
        SENSOR_UNIT: DATA_RATE_MEGABITS_PER_SECOND,
        SENSOR_FACTOR: 125000,
        SENSOR_ICON: "mdi:upload-network",
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_RX_BYTES: {
        SENSOR_NAME: "AsusWrt download",
        SENSOR_UNIT: DATA_GIGABYTES,
        SENSOR_FACTOR: 1000000000,
        SENSOR_ICON: "mdi:download-network",
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_TX_BYTES: {
        SENSOR_NAME: "AsusWrt upload",
        SENSOR_UNIT: DATA_GIGABYTES,
        SENSOR_FACTOR: 1000000000,
        SENSOR_ICON: "mdi:upload-network",
        SENSOR_DEVICE_CLASS: None,
    },
}

TEMPERATURE_SENSOR_TEMPLATE = {
    SENSOR_NAME: None,
    SENSOR_UNIT: TEMP_CELSIUS,
    SENSOR_FACTOR: None,
    SENSOR_ICON: "mdi:thermometer",
    SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""
    router = hass.data[DOMAIN][entry.unique_id]
    entities = []

    for sensor_key in CONNECTION_SENSORS:
        entities.append(
            AsusWrtSensor(router, sensor_key, CONNECTION_SENSORS[sensor_key])
        )

    for sensor_name in router.sensors_temperature:
        entities.append(
            AsusWrtSensor(
                router,
                sensor_name,
                {**TEMPERATURE_SENSOR_TEMPLATE, SENSOR_NAME: f"AsusWrt {sensor_name}"},
            )
        )

    async_add_entities(entities, True)


class AsusWrtSensor(Entity):
    """Representation of a AsusWrt sensor."""

    def __init__(
        self, router: AsusWrtRouter, sensor_type: str, sensor: Dict[str, any]
    ) -> None:
        """Initialize a AsusWrt sensor."""
        self._state = None
        self._router = router
        self._sensor_type = sensor_type
        self._name = sensor[SENSOR_NAME]
        self._unit = sensor[SENSOR_UNIT]
        self._factor = sensor[SENSOR_FACTOR]
        self._icon = sensor[SENSOR_ICON]
        self._device_class = sensor[SENSOR_DEVICE_CLASS]
        self._unique_id = f"{self._router.host} {self._name}"

    @callback
    def async_update_state(self) -> None:
        """Update the AsusWrt sensor."""
        state = self._router.sensors[self._sensor_type]
        if self._factor:
            self._state = round(state / self._factor, 2)
        else:
            self._state = state

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state."""
        return self._state

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
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return self._router.device_info

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_sensor_update,
                self.async_on_demand_update,
            )
        )
