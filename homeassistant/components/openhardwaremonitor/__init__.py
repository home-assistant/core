"""The Open Hardware Monitor component."""

from __future__ import annotations

from datetime import timedelta

from pyopenhardwaremonitor.api import OpenHardwareMonitorAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle

from .const import DOMAIN, GROUP_DEVICES_PER_DEPTH_LEVEL
from .coordinator import OpenHardwareMonitorDataCoordinator, OpenHardwareMonitorConfigEntry
from .sensor import OpenHardwareMonitorSensorDevice

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)
SCAN_INTERVAL = timedelta(seconds=30)
RETRY_INTERVAL = timedelta(seconds=30)
PLATFORMS = [Platform.SENSOR]

OHM_VALUE = "Value"
OHM_MIN = "Min"
OHM_MAX = "Max"
OHM_CHILDREN = "Children"
OHM_NAME = "Text"
OHM_ID = "id"



async def async_setup_entry(hass: HomeAssistant, entry: OpenHardwareMonitorConfigEntry) -> bool:
    """Set up OpenHardwareMonitor from a config entry."""
    # data_handler = OpenHardwareMonitorDataHandler(entry, hass)
    # await data_handler.initialize()
    # if data_handler.data is None:
    #     raise ConfigEntryNotReady

    coordinator = OpenHardwareMonitorDataCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    if not coordinator.data:
        raise ConfigEntryNotReady

    # d = coordinator.data
    # first_node = d[list(d)[0]]
    # if first_node and entry.data.get(GROUP_DEVICES_PER_DEPTH_LEVEL) > 1:
    #     # Create the 'Computer' device here, if should group in multiple devices
    #     host = entry.data[CONF_HOST]
    #     port = entry.data[CONF_PORT]
    #     device_name = first_node["Text"]

    #     device_registry = dr.async_get(hass)
    #     coordinator.set_computer_device(
    #         device_registry.async_get_or_create(
    #             config_entry_id=entry.entry_id,
    #             name=device_name,
    #             identifiers={(DOMAIN, f"{entry.entry_id}_{host}:{port}")},
    #             manufacturer="Computer",
    #         )
    #     )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # convert title and unique_id to string
    if config_entry.version == 1:
        if isinstance(config_entry.unique_id, int):
            hass.config_entries.async_update_entry(  # type: ignore[unreachable]
                config_entry,
                unique_id=str(config_entry.unique_id),
                title=str(config_entry.title),
            )
    return True


# deprecated
class OpenHardwareMonitorDataHandler:
    """Class used to pull data from OHM and create sensors."""

    def __init__(self, config_entry, hass):
        """Initialize the Open Hardware Monitor data-handler."""
        self.data = None
        self._config_entry = config_entry
        self._config = config_entry.data
        self._hass = hass
        self.devices = []

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Hit by the timer with the configured interval."""
        if self.data is None:
            await self.initialize()
        else:
            await self.refresh()

    async def refresh(self):
        """Get data from OHM remote server."""
        session = async_get_clientsession(self._hass)
        api = OpenHardwareMonitorAPI(
            self._config.get(CONF_HOST), self._config.get(CONF_PORT), session=session
        )
        self.data = await api.get_data()

    async def initialize(self):
        """Parse of the sensors and adding of devices."""
        await self.refresh()

        if self.data is None:
            return

        self.entities = self.parse_children(self.data, [], [], [])

    def parse_children(self, json, devices, path, names):
        """Recursively loop through child objects, finding the values."""
        result = devices.copy()

        id = str(json[OHM_ID])
        if id == "1" and self._config.get(GROUP_DEVICES_PER_DEPTH_LEVEL) > 1:
            # Create the 'Computer' device here, if should group in multiple devices
            host = self._config[CONF_HOST]
            port = self._config[CONF_PORT]

            device_registry = dr.async_get(self._hass)
            device_registry.async_get_or_create(
                config_entry_id=self._config_entry.entry_id,
                name=json[OHM_NAME],
                identifiers={(DOMAIN, f"{host}:{port}")},
                manufacturer="Computer",
            )

        if json[OHM_CHILDREN]:
            for child_index in range(len(json[OHM_CHILDREN])):
                child_path = path.copy()
                child_path.append(child_index)

                child_names = names.copy()
                if path:
                    child_names.append(json[OHM_NAME])

                obj = json[OHM_CHILDREN][child_index]

                added_devices = self.parse_children(
                    obj, devices, child_path, child_names
                )

                result = result + added_devices
            return result

        if json[OHM_VALUE].find(" ") == -1:
            return result

        unit_of_measurement = json[OHM_VALUE].split(" ")[1]
        child_names = names.copy()
        child_names.append(json[OHM_NAME])
        fullname = " ".join(child_names)

        dev = OpenHardwareMonitorSensorDevice(
            data=self, name=fullname, path=path, unit_of_measurement=unit_of_measurement, id=id, child_names=child_names, json=json
        )

        result.append(dev)
        return result
