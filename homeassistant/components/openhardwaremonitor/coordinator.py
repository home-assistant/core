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
from .types import DataNode, SensorNode, SensorType

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
        self._config_entry_id = config_entry.entry_id
        self._grouping = int(self._config.get(GROUP_DEVICES_PER_DEPTH_LEVEL, 2))
        self._computers: dict[str, dr.DeviceEntry] = {}

    async def _async_update_data(self) -> dict[str, SensorNode]:
        """Get data from OHM remote server."""
        session = async_get_clientsession(self.hass)
        api = OpenHardwareMonitorAPI(
            self._config.get(CONF_HOST), self._config.get(CONF_PORT), session=session
        )
        data: DataNode = await api.get_data()

        if not self._computers:
            computers = {}
            computer_names = OpenHardwareMonitorDataCoordinator._parse_computer_nodes(
                data
            )
            if self._grouping > 0:
                # Create the 'Computer' device here
                device_registry = dr.async_get(self.hass)
                for name in computer_names:
                    de = device_registry.async_get_or_create(
                        config_entry_id=self._config_entry_id,
                        name=name,
                        identifiers={(DOMAIN, f"{self._config_entry_id}__{name}")},
                        manufacturer="Computer",
                    )
                    _LOGGER.info("get/create Device: %s %s", de.name, de.created_at)
                    computers[name] = de
            _LOGGER.info("Computers: %s", list(computers.keys()))
            self._computers = computers

        sensor_nodes = [
            n
            for c in data["Children"]
            for n in OpenHardwareMonitorDataCoordinator._parse_sensor_nodes(c)
        ]

        return {n["FullName"]: n for n in sensor_nodes}

    def resolve_device_info_for_node(self, node: SensorNode) -> dr.DeviceInfo | None:
        """Get the appropriate device for specified SensorNode."""
        if self._grouping == 0:
            return None

        computer = self._computers.get(node["ComputerName"])
        if self._grouping == 1:
            # Computer device
            if computer:
                return dr.DeviceInfo(
                    identifiers=computer.identifiers,
                    name=computer.name,
                    manufacturer=computer.manufacturer,
                    model=computer.model,
                )
            return None

        paths = node["Paths"]
        device_name = " ".join(paths[: self._grouping])
        manufacturer = "Hardware" if self._grouping == 2 else "Group"
        model = paths[1] if self._grouping == 2 else None
        via_device = (DOMAIN, dict(computer.identifiers)[DOMAIN]) if computer else None

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
            return []
        return [node["Text"] for node in root_node["Children"] if node.get("Text")]

    @staticmethod
    def _parse_sensor_nodes(
        node: DataNode, paths: list[str] | None = None
    ) -> list[SensorNode]:
        """Recursively loop through child objects, finding the values."""
        result: list[SensorNode] = []
        if paths is None:
            paths = []

        if node.get("Children"):
            for n in node["Children"]:
                sub_nodes = OpenHardwareMonitorDataCoordinator._parse_sensor_nodes(
                    n, [*paths, node["Text"]]
                )
                result.extend(sub_nodes)
        elif node.get("Value"):
            sensor = SensorNode(
                **node,
                Paths=paths,
                FullName=" ".join([*paths, node["Text"]]),
                ComputerName=paths[0],
                Type=SensorType(node.get("Type")) if node.get("Type") else None,
            )
            result.append(sensor)
        return result

    def get_sensor_node(self, fullname: str) -> SensorNode | None:
        """Get the data for specific sensor."""
        return self.data.get(fullname)
