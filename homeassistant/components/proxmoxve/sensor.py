"""Sensor to read Proxmox VE data."""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_HOST, CONF_PORT

from . import CONF_CONTAINERS, CONF_NODES, CONF_STORAGE, PROXMOX_CLIENTS, ProxmoxItemType

ATTRIBUTION = "Data provided by Proxmox VE"
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    sensors = []

    for entry in discovery_info["entries"]:
        port = entry[CONF_PORT]

        for node in entry[CONF_NODES]:
            for storage in node[CONF_STORAGE]:
                sensors.append(
                    ProxmoxSensor(
                        hass.data[PROXMOX_CLIENTS][f"{entry[CONF_HOST]}:{port}"],
                        node["node"],
                        ProxmoxItemType.storage,
                        storage,
                    )
                )

    add_entities(sensors, True)


class ProxmoxSensor(Entity):
    """A binary sensor for reading Proxmox VE data."""

    def __init__(self, proxmox_client, item_node, item_type, item_name):
        """Initialize the binary sensor."""
        self._proxmox_client = proxmox_client
        self._item_node = item_node
        self._item_type = item_type
        self._storagename = item_name

        self._name = None
        self._maxdisk = None
        self._usedisk = None
        self._state = None

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return '%'

    @property
    def state(self):
        """Return percent of storage used if storage is available."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            "node": self._item_node,
            "storagename": self._storagename,
            "type": self._item_type.name,
            "gb_total": self._total,
            "gb_used": self._used,
            "gb_avail": self._avail,
            "content": self._content,
            "type": self._type,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def update(self):
        """Check if the storage exists."""
        item = self.poll_item()

        if item is None:
            _LOGGER.warning("Failed to poll storage %s", self._storagename)
            return

        self._state = round( item["used_fraction"] * 100, 1)
        self._total = round( item["total"] / 1024/1024/1024, 1)
        self._used = round( item["used"] / 1024/1024/1024, 1)
        self._avail = round( item["avail"] / 1024/1024/1024, 1)
        self._content = item["content"]
        self._type = item["type"]

    def poll_item(self):
        """Find the storage with the set name."""
        items = (
            self._proxmox_client.get_api_client()
            .nodes(self._item_node)
            .get(self._item_type.name)
        )
        item = next(
            (item for item in items if item["storage"] == str(self._storagename)), None
        )

        if item is None:
            _LOGGER.warning("Couldn't find storage with the name %s", self._storagename)
            return None

        if self._name is None:
            self._name = f"{self._item_node} storage {self._storagename}"

        return item
