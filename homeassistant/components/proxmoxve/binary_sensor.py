"""Binary sensor to read Proxmox VE data."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_HOST, CONF_PORT

from .const import (
    ATTRIBUTION,
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_VMS,
    GUESTTYPE_LXC,
    GUESTTYPE_QEMU,
    PROXMOX_CLIENTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor platform."""

    sensors = []

    for entry in discovery_info["entries"]:
        port = entry[CONF_PORT]

        for node in entry[CONF_NODES]:
            for virtual_machine in node[CONF_VMS]:
                sensors.append(
                    ProxmoxBinarySensor(
                        hass.data[PROXMOX_CLIENTS][f"{entry[CONF_HOST]}:{port}"],
                        node[CONF_NODE],
                        GUESTTYPE_QEMU,
                        virtual_machine,
                    )
                )

            for container in node[CONF_CONTAINERS]:
                sensors.append(
                    ProxmoxBinarySensor(
                        hass.data[PROXMOX_CLIENTS][f"{entry[CONF_HOST]}:{port}"],
                        node[CONF_NODE],
                        GUESTTYPE_LXC,
                        container,
                    )
                )

    async_add_devices(sensors, True)


class ProxmoxBinarySensor(BinarySensorEntity):
    """A binary sensor for reading Proxmox VE data."""

    def __init__(self, proxmox_client, item_node, item_type, item_id):
        """Initialize the binary sensor."""
        self._proxmox_client = proxmox_client
        self._item_node = item_node
        self._item_type = item_type
        self._item_id = item_id

        self._cpus = None
        self._memory = None
        self._name = None
        self._vmname = None

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
            "type": self._item_type,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def update(self):
        """Check if the VM/Container is running."""
        item = self.poll_item()

        if item is None:
            _LOGGER.warning("Failed to poll VM/container %s", self._item_id)
            return

        self._state = item["status"] == "running"

    def poll_item(self):
        """Find the VM/Container with the set item_id."""
        items = (
            self._proxmox_client.get_api_client()
            .nodes(self._item_node)
            .get(self._item_type)
        )
        item = next(
            (item for item in items if item["vmid"] == str(self._item_id)), None
        )

        if item is None:
            _LOGGER.warning("Couldn't find VM/Container with the ID %s", self._item_id)
            return None

        self._vmname = item.get("name")
        self._name = f"{self._item_node} {self._vmname} running"

        return item
