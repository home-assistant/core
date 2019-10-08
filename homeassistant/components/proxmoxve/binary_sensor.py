"""Binary sensor to read Proxmox VE data."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_HOST, CONF_PORT, ATTR_ATTRIBUTION

from . import ProxmoxItemType, PROXMOX_CLIENTS, CONF_NODES, CONF_VMS, CONF_CONTAINERS

ATTRIBUTION = "Data provided by Proxmox VE"
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    for entry in discovery_info["entries"]:
        port = entry[CONF_PORT]

        sensors = []

        for node in entry[CONF_NODES]:
            for vm in node[CONF_VMS]:
                sensors.append(
                    ProxmoxBinarySensor(
                        PROXMOX_CLIENTS[f"{entry[CONF_HOST]}:{str(port)}"],
                        node["node"],
                        ProxmoxItemType.qemu,
                        vm,
                    )
                )

            for container in node[CONF_CONTAINERS]:
                sensors.append(
                    ProxmoxBinarySensor(
                        PROXMOX_CLIENTS[f"{entry[CONF_HOST]}:{str(port)}"],
                        node["node"],
                        ProxmoxItemType.lxc,
                        container,
                    )
                )

        add_entities(sensors, True)


class ProxmoxBinarySensor(BinarySensorDevice):
    """A binary sensor for reading Proxmox VE data."""

    def __init__(self, proxmox_client, item_node, item_type, item_id):
        """Initialize the binary sensor."""

        self._proxmox_client = proxmox_client
        self._item_node = item_node
        self._item_type = item_type
        self._item_id = item_id

        item = self.poll_item()

        if item is None:
            _LOGGER.warning("Couldn't find VM/Container with the ID %s", self._item_id)

        self._vmname = item["name"]
        self._name = f"{self._item_node} {self._vmname} running"

        self._state = None

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def is_on(self):
        """Return true if VM/container is running."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            "node": self._item_node,
            "vmid": self._item_id,
            "vmname": self._vmname,
            "type": self._item_type.name,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def update(self):
        """Check if the VM/Container is running."""
        self._state = self.poll_item()["status"] == "running"

    def poll_item(self):
        """Find the VM/Container with the set item_id."""
        items = (
            self._proxmox_client.get_api_client()
            .nodes(self._item_node)
            .get(self._item_type.name)
        )
        item = next(
            (item for item in items if item["vmid"] == str(self._item_id)), None
        )

        return item
