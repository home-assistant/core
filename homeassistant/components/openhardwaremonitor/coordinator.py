"""The Open Hardware Monitor component."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyopenhardwaremonitor.api import OpenHardwareMonitorAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import Throttle

from .const import DOMAIN, GROUP_DEVICES_PER_DEPTH_LEVEL
from .types import DataNode, SensorNode

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
_LOGGER = logging.getLogger(__name__)

type OpenHardwareMonitorConfigEntry = ConfigEntry[OpenHardwareMonitorDataCoordinator]


class OpenHardwareMonitorDataCoordinator(DataUpdateCoordinator[dict[str, SensorNode]]):
    """Class used to pull data from OHM."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Open Hardware Monitor data coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name="OpenHardwareMonitor",
            update_interval=SCAN_INTERVAL,
        )
        self._config = config_entry.data
        self._grouping = self._config.get(GROUP_DEVICES_PER_DEPTH_LEVEL, 2)
        self._computers: dict[str, dr.DeviceEntry] = None

    async def _async_update_data(self) -> dict[str, SensorNode]:
        """Get data from OHM remote server."""
        session = async_get_clientsession(self.hass)
        api = OpenHardwareMonitorAPI(
            self._config.get(CONF_HOST), self._config.get(CONF_PORT), session=session
        )
        data: DataNode = await api.get_data()
        # _LOGGER.debug("DATA: %s", data)

        if not self._computers:
            c = {}
            computer_names = OpenHardwareMonitorDataCoordinator._parse_computer_nodes(
                data
            )
            if self.config_entry.data.get(GROUP_DEVICES_PER_DEPTH_LEVEL) > 0:
                # Create the 'Computer' device here
                device_registry = dr.async_get(self.hass)
                for name in computer_names:
                    de = device_registry.async_get_or_create(
                        config_entry_id=self.config_entry.entry_id,
                        name=name,
                        identifiers={(DOMAIN, f"{self.config_entry.entry_id}__{name}")},
                        manufacturer="Computer",
                    )
                    _LOGGER.info("Get/create device: %s %s", de.name, de.created_at)
                    c[name] = de
            _LOGGER.info("Computers: %s", c)
            self._computers = c

        sensor_nodes = OpenHardwareMonitorDataCoordinator._parse_sensor_nodes(data)
        sensor_nodes = sensor_nodes[:4]  # only test with 1

        sensor_data = OpenHardwareMonitorDataCoordinator._format_as_dict(sensor_nodes)
        _LOGGER.info("Sensor data: %s", sensor_data)
        return sensor_data

    def resolve_device_info_for_node(self, node: SensorNode) -> dr.DeviceEntry:
        if self._grouping == 0:
            return None

        paths = node["Paths"]
        device_name = " ".join(paths[0: self._grouping])
        _LOGGER.info("Resolved device name for: %s => %s", paths, device_name)

        computer_device = self._computers.get(node["ComputerName"])
        if computer_device:
            computer_device_domain_id = dict(computer_device.identifiers)[DOMAIN]
            via_device = (DOMAIN, computer_device_domain_id)
        else:
            via_device = None

        manufacturer = ""
        if self._grouping == 1:
            # Computer device
            d = dr.DeviceInfo(
                # identifiers={(DOMAIN, f"{host}:{port}")},
                # name=str(child_names[0]),
                # manufacturer="Computer",
                identifiers=computer_device.identifiers,
                name=computer_device.name,
                manufacturer=computer_device.manufacturer,
            ) if computer_device else None
            _LOGGER.info("DeviceInfo: %s", d)
            # d = computer_device
            # _LOGGER.info("DeviceEntry: %s", d)
            return d

        if self._grouping == 2:
            manufacturer = "Hardware"
        else:
            manufacturer = "Group"

        model = ""
        if self._grouping == 2:
            model = paths[1]

        # Hardware or Group device
        d = dr.DeviceInfo(
            identifiers={(DOMAIN, device_name)},
            via_device=via_device,
            name=device_name,
            manufacturer=manufacturer,
            model=model,
        )
        _LOGGER.info("Sensor device: %s", d)
        return d

    @staticmethod
    def _parse_computer_nodes(root_node: DataNode) -> list[str]:
        if not root_node or not root_node.get("Children"):
            return None
        return [node["Text"] for node in root_node["Children"] if node.get("Text")]

    @staticmethod
    def _parse_sensor_nodes(
        node: DataNode, path: list[str] | None = None
    ) -> list[SensorNode]:
        result: list[SensorNode] = []
        if path is None:
            path = []
        else:
            path.append(node["Text"])

        if node.get("Children", None):
            for n in node["Children"]:
                sub_nodes = OpenHardwareMonitorDataCoordinator._parse_sensor_nodes(
                    n, path.copy()
                )
                result.extend(sub_nodes)
        elif node.get("Value"):
            sensor = SensorNode(**node)
            del sensor["Children"]
            sensor["Paths"] = path
            sensor["ComputerName"] = path[0]

            # print(sensor)
            result.append(sensor)
        return result

    @staticmethod
    def _format_as_dict(sensor_nodes: list[SensorNode]) -> dict[str, SensorNode]:
        return {" ".join(n["Paths"]): n for n in sensor_nodes}

    def get_sensor_node(self, path_key: str) -> SensorNode | None:
        return self.data.get(path_key)

    # async def refresh(self):
    #     """Get data from OHM remote server."""
    #     session = async_get_clientsession(self.hass)
    #     api = OpenHardwareMonitorAPI(
    #         self._config.get(CONF_HOST), self._config.get(CONF_PORT), session=session
    #     )
    #     self.data = await api.get_data()

    # async def initialize(self):
    #     """Parse of the sensors and adding of devices."""
    #     await self.refresh()

    #     if self.data is None:
    #         return

    #     self.entities = self.parse_children(self.data, [], [], [])

    def parse_children(self, json, devices, path, names):
        """Recursively loop through child objects, finding the values."""
        result = devices.copy()

        id = str(json[OHM_ID])
        if id == "1" and self._config.get(GROUP_DEVICES_PER_DEPTH_LEVEL) > 1:
            # Create the 'Computer' device here, if should group in multiple devices
            host = self._config[CONF_HOST]
            port = self._config[CONF_PORT]

            device_registry = dr.async_get(self.hass)
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

        dev = OpenHardwareMonitorDevice(
            self, fullname, path, unit_of_measurement, id, child_names, json
        )

        result.append(dev)
        return result
