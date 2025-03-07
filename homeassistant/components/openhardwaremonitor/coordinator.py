"""The Open Hardware Monitor component."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyopenhardwaremonitor.api import OpenHardwareMonitorAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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

        sensor_nodes = [
            n
            for c in data["Children"]
            for n in OpenHardwareMonitorDataCoordinator._parse_sensor_nodes(c)
        ]

        # sensor_nodes = sensor_nodes[:4]  # only test with 1
        # _LOGGER.info("Sensor nodes: %s", sensor_nodes)

        sensor_data = OpenHardwareMonitorDataCoordinator._format_as_dict(sensor_nodes)
        _LOGGER.info("Sensor data: %s", sensor_data)
        return sensor_data

    def resolve_device_info_for_node(self, node: SensorNode) -> dr.DeviceEntry:
        if self._grouping == 0:
            return None

        paths = node["Paths"]
        device_name = " ".join(paths[: self._grouping])
        _LOGGER.info("Resolved device name for: %s => %s", paths, device_name)

        computer = self._computers.get(node["ComputerName"])
        if computer:
            computer_device_domain_id = dict(computer.identifiers)[DOMAIN]
            via_device = (DOMAIN, computer_device_domain_id)
        else:
            via_device = None

        if self._grouping == 1:
            # Computer device
            return (
                dr.DeviceInfo(
                    identifiers=computer.identifiers,
                    name=computer.name,
                    manufacturer=computer.manufacturer,
                    model=computer.model,
                )
                if computer
                else None
            )

        if self._grouping == 2:
            manufacturer = "Hardware"
        else:
            manufacturer = "Group"

        model = ""
        if self._grouping == 2:
            model = paths[1]

        # Hardware or Group device
        return dr.DeviceInfo(
            identifiers={(DOMAIN, device_name)},
            via_device=via_device,
            name=device_name,
            manufacturer=manufacturer,
            model=model,
        )

    @staticmethod
    def _parse_computer_nodes(root_node: DataNode) -> list[str]:
        """Get the available computer names in the data."""
        if not root_node or not root_node.get("Children"):
            return None
        return [node["Text"] for node in root_node["Children"] if node.get("Text")]

    @staticmethod
    def _parse_sensor_nodes(
        node: DataNode, paths: list[str] | None = None
    ) -> list[SensorNode]:
        """Recursively loop through child objects, finding the values."""
        result: list[SensorNode] = []
        if paths is None:
            paths = []

        if node.get("Children", None):
            for n in node["Children"]:
                sub_nodes = OpenHardwareMonitorDataCoordinator._parse_sensor_nodes(
                    n, [*paths, node["Text"]]
                )
                result.extend(sub_nodes)
        elif node.get("Value"):
            sensor = SensorNode(**node)
            del sensor["Children"]
            sensor["Paths"] = paths
            sensor["FullName"] = " ".join([*paths, sensor["Text"]])
            sensor["ComputerName"] = paths[0]
            result.append(sensor)
        return result

    @staticmethod
    def _format_as_dict(sensor_nodes: list[SensorNode]) -> dict[str, SensorNode]:
        return {n["FullName"]: n for n in sensor_nodes}

    def get_sensor_node(self, fullname: str) -> SensorNode | None:
        """Get the data for specific sensor."""
        return self.data.get(fullname)
