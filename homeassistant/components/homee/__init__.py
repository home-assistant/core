"""The homee integration."""

from dataclasses import dataclass
import logging
from typing import Any

from pyHomee import Homee
from pyHomee.const import AttributeType, NodeProfile
from pyHomee.model import HomeeAttribute, HomeeNode
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_HOMEE_DATA, CONF_ADD_HOMEE_DATA, DOMAIN
from .helpers import get_name_for_enum

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["cover"]


@dataclass
class HomeeRuntimeData:
    """Homee data class."""

    homee: Homee


type HomeeConfigEntry = ConfigEntry[HomeeRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the homee component."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: HomeeConfigEntry) -> bool:
    """Set up homee from a config entry."""
    # Create the Homee api object using host, user,
    # password & pyHomee instance from the config
    homee = Homee(
        host=entry.data[CONF_HOST],
        user=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        device="pymee_" + hass.config.location_name,
        reconnect_interval=10,
        max_retries=100,
    )

    # Start the homee websocket connection as a new task
    # and wait until we are connected
    hass.loop.create_task(homee.run())
    await homee.wait_until_connected()

    # Log info about nodes, to facilitate recognition of unknown nodes.
    for node in homee.nodes:
        _LOGGER.info(
            "Found node %s, with following Data: %s",
            node.name,
            node.raw_data,
        )

    entry.runtime_data = HomeeRuntimeData(homee)

    # create device register entry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={
            (dr.CONNECTION_NETWORK_MAC, dr.format_mac(homee.settings.mac_address))
        },
        identifiers={(DOMAIN, homee.settings.uid)},
        manufacturer="homee",
        name=homee.settings.homee_name,
        model="homee",
        sw_version=homee.settings.version,
        hw_version="TBD",
    )

    # Forward entry setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomeeConfigEntry) -> bool:
    """Unload a homee config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Get Homee object and remove it from data
        homee: Homee = entry.runtime_data.homee

        # Schedule homee disconnect
        homee.disconnect()

    return unload_ok


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload homee integration after config change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: HomeeConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    homee = config_entry.runtime_data.homee
    model = NodeProfile[device_entry.model].value
    for node in homee.nodes:
        # 'identifiers' is a set of tuples, so we need to check for the tuple.
        if ("homee", node.id) in device_entry.identifiers and node.profile == model:
            # If Node is still present in Homee, don't delete.
            return False

    return True


class HomeeNodeEntity:
    """Representation of a Node in Homee."""

    _unrecorded_attributes = frozenset({ATTR_HOMEE_DATA})

    def __init__(
        self, node: HomeeNode, entity: Entity, entry: HomeeConfigEntry
    ) -> None:
        """Initialize the wrapper using a HomeeNode and target entity."""
        self._node = node
        self._entity = entity
        self._clear_node_listener = None
        self._attr_unique_id = node.id
        self._entry = entry

        self._homee_data = {
            "id": node.id,
            "name": node.name,
            "profile": node.profile,
            "attributes": [{"id": a.id, "type": a.type} for a in node.attributes],
        }

    async def async_added_to_hass(self) -> None:
        """Add the homee binary sensor device to home assistant."""
        self.register_listener()

    async def async_will_remove_from_hass(self):
        """Cleanup the entity."""
        self.clear_listener()

    @property
    def device_info(self):
        """Holds the available information about the device."""
        if self.has_attribute(AttributeType.FIRMWARE_REVISION):
            sw_version = self.attribute(AttributeType.FIRMWARE_REVISION)
        elif self.has_attribute(AttributeType.SOFTWARE_REVISION):
            sw_version = self.attribute(AttributeType.SOFTWARE_REVISION)
        else:
            sw_version = "undefined"

        return {
            "identifiers": {
                # Serial numbers are unique IDs within a specific domain
                (DOMAIN, self._node.id)
            },
            "name": self._node.name,
            "manufacturer": "unknown",
            "model": get_name_for_enum(NodeProfile, self._homee_data["profile"]),
            "sw_version": sw_version,
            "via_device": (DOMAIN, self._entry.unique_id),
        }

    @property
    def available(self) -> bool:
        """Return the availability of the underlying node."""
        return self._node.state <= 1

    @property
    def should_poll(self) -> bool:
        """Return if the entity should poll."""
        return False

    @property
    def raw_data(self):
        """Return the raw data of the node."""
        return self._node.raw_data

    @property
    def extra_state_attributes(self) -> dict[str, dict[str, Any]] | None:
        """Return entity specific state attributes."""
        data = {}

        if self._entry.options.get(CONF_ADD_HOMEE_DATA, False):
            data[ATTR_HOMEE_DATA] = self._homee_data

        return data if data else None

    async def async_update(self):
        """Fetch new state data for this node."""
        homee = self._entry.runtime_data.homee
        await homee.update_node(self._node.id)

    def register_listener(self):
        """Register the on_changed listener on the node."""
        self._clear_node_listener = self._node.add_on_changed_listener(
            self._on_node_updated
        )

    def clear_listener(self):
        """Clear the on_changed listener on the node."""
        if self._clear_node_listener is not None:
            self._clear_node_listener()

    def attribute(self, attribute_type):
        """Try to get the current value of the attribute of the given type."""
        try:
            attribute = self._node.get_attribute_by_type(attribute_type)
        except KeyError:
            raise AttributeNotFoundException(attribute_type) from None

        # If the unit of the attribute is 'text', it is stored in .data
        if attribute.unit == "text":
            return self._node.get_attribute_by_type(attribute_type).data

        return self._node.get_attribute_by_type(attribute_type).current_value

    def get_attribute(self, attribute_type):
        """Get the attribute object of the given type."""
        return self._node.get_attribute_by_type(attribute_type)

    def has_attribute(self, attribute_type):
        """Check if an attribute of the given type exists."""
        return attribute_type in self._node.attribute_map

    def is_reversed(self, attribute_type) -> bool:
        """Check if movement direction is reversed."""
        attribute = self._node.get_attribute_by_type(attribute_type)
        if hasattr(attribute.options, "reverse_control_ui"):
            if attribute.options.reverse_control_ui:
                return True

        return False

    async def async_set_value(self, attribute_type: int, value: float):
        """Set an attribute value on the homee node."""
        await self.async_set_value_by_id(self.get_attribute(attribute_type).id, value)

    async def async_set_value_by_id(self, attribute_id: int, value: float):
        """Set an attribute value on the homee node."""
        homee = self._entry.runtime_data.homee
        await homee.set_value(self._node.id, attribute_id, value)

    def _on_node_updated(self, node: HomeeNode, attribute: HomeeAttribute):
        self._entity.schedule_update_ha_state()


class AttributeNotFoundException(Exception):
    """Raised if a requested attribute does not exist on a homee node."""

    def __init__(self, attributeType) -> None:
        """Initialize the exception."""
        self.attributeType = attributeType
