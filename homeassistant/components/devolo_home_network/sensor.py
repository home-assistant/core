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
        "name": "Home Network Devices",
        "update_call": "plcnet.async_get_network_overview",
    },
    {"name": "Wifi Clients", "update_call": "device.async_get_wifi_connected_station"},
    # "Neighbor Wifi Networks",
]


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    entities = []
    device = hass.data[DOMAIN][entry.entry_id]
    print(entry.entry_id)

    # async def async_update_data():
    #     """Fetch data from API endpoint.

    #     This is the place to pre-process the data to lookup tables
    #     so entities can quickly look up their data.
    #     """
    #     try:
    #         async with async_timeout.timeout(60):
    #             calls = await asyncio.gather(
    #                 device.plcnet.async_get_network_overview(),
    #                 device.device.async_get_wifi_connected_station(),
    #             )
    #             #  device.device.async_get_wifi_neighbor_access_points())
    #             dict_call = {}
    #             for call in calls:
    #                 for e in call:
    #                     dict_call[e] = call[e]
    #             # We pre process our data - Think about it!
    #             calls[0] = {
    #                 "Home Network Devices": len(calls[0]["network"]["data_rates"]) // 2
    #             }
    #             calls[1] = {"Wifi Clients": len(calls[1]["connected_stations"])}
    #             # calls[2] = {"Neighbor Wifi Networks": len(calls[2]["neighbor_aps"])}
    #             return calls
    #     except KeyError as err:
    #         raise UpdateFailed(f"Error communicating with API: {err}")

    # coordinator = DataUpdateCoordinator(
    #     hass,
    #     _LOGGER,
    #     # Name of the data. For logging purposes.
    #     name="sensor",
    #     update_method=async_update_data,
    #     # Polling interval. Will only be polled if there are subscribers.
    #     update_interval=timedelta(seconds=10),
    # )

    # await coordinator.async_refresh()
    print(device)
    for idx, sensor in enumerate(SENSORS):
        print(device.mac)
        entities.append(DevoloDevice(device, idx, sensor, entry.title))
    async_add_entities(entities, True)


class DevoloDevice(Entity):
    """Representation of a devolo home network device."""

    def __init__(self, device, index, sensor, device_name):
        """Initialize a devolo home network device."""
        print(device)
        self.device = device
        self._unique_id = device.mac
        print(self._unique_id)
        self._state = ""
        self._index = index
        self.device_name = device_name
        self._name = f"{self.device_name}_{sensor['name']}"
        self._sensor = sensor

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self.device_name,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._unique_id}_{self._name}"

    @property
    def state(self):
        """Return the state of the device."""
        print(f"STATE {self._name} {self.device_name}")
        return self._state

    async def async_update(self):
        """Update the value async."""
        value = await eval("self.device." + SENSORS[self._index]["update_call"])()
        try:
            self._state = len(value["network"]["data_rates"]) // 2
        except KeyError:
            self._state = len(value["connected_stations"])
