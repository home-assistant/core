"""Platform for sensor integration."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


SENSORS = [
    {
        "plc": {
            "name": "Home Network Devices",
            "update_call": "async_get_network_overview",
            "value_expression": lambda x: len(
                {y["mac_address_from"] for y in x["network"]["data_rates"]}
            ),
        }
    },
    {
        "device": {
            "name": "Wifi Clients",
            "update_call": "async_get_wifi_connected_station",
            "value_expression": lambda x: (len(x["connected_stations"])),
        }
    },
    # "Neighbor Wifi Networks",
]


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    entities = []
    device = hass.data[DOMAIN][entry.entry_id]
    for idx, sensor in enumerate(SENSORS):
        try:
            properties = sensor["plc"]
            entities.append(
                DevoloPlcEntity(
                    hass.data[DOMAIN][entry.entry_id], idx, properties, entry.title
                )
            )
        except KeyError:
            properties = sensor["device"]
            entities.append(
                DevoloDeviceEntity(
                    hass.data[DOMAIN][entry.entry_id], idx, properties, entry.title
                )
            )
    async_add_entities(entities, True)


class DevoloDevice(Entity):
    """Representation of a devolo home network device."""

    def __init__(self, device, index, sensor, device_name):
        """Initialize a devolo home network device."""
        self.device = device
        self._state = ""
        self._index = index
        self.device_name = device_name
        self._name = sensor["name"]
        self._unique_id = f"{self.device.serial_number}_{self._name}"
        self._sensor = sensor
        self._update_call = sensor["update_call"]
        self._value_expression = sensor["value_expression"]

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.device.serial_number)},
            "name": self.device_name,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the device."""
        # print(f"STATE {self._name} {self.device_name}")
        return self._state


class DevoloPlcEntity(DevoloDevice):
    def __init__(self, device, index, sensor, device_name):
        super(self.__class__, self).__init__(device, index, sensor, device_name)

    async def async_update(self):
        """Update the value async."""
        call = getattr(self.device.plcnet, self._update_call)
        value = await call()
        try:
            self._state = self._value_expression(value)
        except KeyError:
            self._state = 0


class DevoloDeviceEntity(DevoloDevice):
    def __init__(self, device, index, sensor, device_name):
        super(self.__class__, self).__init__(device, index, sensor, device_name)
        self._update_call = sensor["update_call"]

    async def async_update(self):
        """Update the value async."""
        call = getattr(self.device.device, self._update_call)
        value = await call()
        try:
            self._state = self._value_expression(value)
        except KeyError:
            self._state = 0
