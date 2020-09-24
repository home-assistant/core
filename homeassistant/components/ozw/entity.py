"""Generic Z-Wave Entity Classes."""

import copy
import logging

from openzwavemqtt.const import (
    EVENT_INSTANCE_STATUS_CHANGED,
    EVENT_VALUE_CHANGED,
    OZW_READY_STATES,
    CommandClass,
    ValueIndex,
    ValueType,
)
from openzwavemqtt.models.node import OZWNode
from openzwavemqtt.models.value import OZWValue

from homeassistant.components.websocket_api.const import (
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from . import const
from .const import DOMAIN, PLATFORMS
from .discovery import check_node_schema, check_value_schema

_LOGGER = logging.getLogger(__name__)
OZW_READY_STATES_VALUES = {st.value for st in OZW_READY_STATES}


class ZWaveDeviceEntityValues:
    """Manages entity access to the underlying Z-Wave value objects."""

    def __init__(self, hass, options, schema, primary_value):
        """Initialize the values object with the passed entity schema."""
        self._hass = hass
        self._entity_created = False
        self._schema = copy.deepcopy(schema)
        self._values = {}
        self.options = options

        # Go through values listed in the discovery schema, initialize them,
        # and add a check to the schema to make sure the Instance matches.
        for name, disc_settings in self._schema[const.DISC_VALUES].items():
            self._values[name] = None
            disc_settings[const.DISC_INSTANCE] = (primary_value.instance,)

        self._values[const.DISC_PRIMARY] = primary_value
        self._node = primary_value.node
        self._schema[const.DISC_NODE_ID] = [self._node.node_id]

    def async_setup(self):
        """Set up values instance."""
        # Check values that have already been discovered for node
        # and see if they match the schema and need added to the entity.
        for value in self._node.values():
            self.async_check_value(value)

        # Check if all the _required_ values in the schema are present and
        # create the entity.
        self._async_check_entity_ready()

    def __getattr__(self, name):
        """Get the specified value for this entity."""
        return self._values.get(name, None)

    def __iter__(self):
        """Allow iteration over all values."""
        return iter(self._values.values())

    def __contains__(self, name):
        """Check if the specified name/key exists in the values."""
        return name in self._values

    @callback
    def async_check_value(self, value):
        """Check if the new value matches a missing value for this entity.

        If a match is found, it is added to the values mapping.
        """
        # Make sure the node matches the schema for this entity.
        if not check_node_schema(value.node, self._schema):
            return

        # Go through the possible values for this entity defined by the schema.
        for name in self._values:
            # Skip if it's already been added.
            if self._values[name] is not None:
                continue
            # Skip if the value doesn't match the schema.
            if not check_value_schema(value, self._schema[const.DISC_VALUES][name]):
                continue

            # Add value to mapping.
            self._values[name] = value

            # If the entity has already been created, notify it of the new value.
            if self._entity_created:
                async_dispatcher_send(
                    self._hass, f"{DOMAIN}_{self.values_id}_value_added"
                )

            # Check if entity has all required values and create the entity if needed.
            self._async_check_entity_ready()

    @callback
    def _async_check_entity_ready(self):
        """Check if all required values are discovered and create entity."""
        # Abort if the entity has already been created
        if self._entity_created:
            return

        # Go through values defined in the schema and abort if a required value is missing.
        for name, disc_settings in self._schema[const.DISC_VALUES].items():
            if self._values[name] is None and not disc_settings.get(
                const.DISC_OPTIONAL
            ):
                return

        # We have all the required values, so create the entity.
        component = self._schema[const.DISC_COMPONENT]

        _LOGGER.debug(
            "Adding Node_id=%s Generic_command_class=%s, "
            "Specific_command_class=%s, "
            "Command_class=%s, Index=%s, Value type=%s, "
            "Genre=%s as %s",
            self._node.node_id,
            self._node.node_generic,
            self._node.node_specific,
            self.primary.command_class,
            self.primary.index,
            self.primary.type,
            self.primary.genre,
            component,
        )
        self._entity_created = True

        if component in PLATFORMS:
            async_dispatcher_send(self._hass, f"{DOMAIN}_new_{component}", self)

    @property
    def values_id(self):
        """Identification for this values collection."""
        return create_value_id(self.primary)


class ZWaveDeviceEntity(Entity):
    """Generic Entity Class for a Z-Wave Device."""

    def __init__(self, values):
        """Initialize a generic Z-Wave device entity."""
        self.values = values
        self.options = values.options

    @callback
    def on_value_update(self):
        """Call when a value is added/updated in the entity EntityValues Collection.

        To be overridden by platforms needing this event.
        """

    async def async_added_to_hass(self):
        """Call when entity is added."""
        # Add dispatcher and OZW listeners callbacks.
        # Add to on_remove so they will be cleaned up on entity removal.
        self.async_on_remove(
            self.options.listen(EVENT_VALUE_CHANGED, self._value_changed)
        )
        self.async_on_remove(
            self.options.listen(EVENT_INSTANCE_STATUS_CHANGED, self._instance_updated)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, const.SIGNAL_DELETE_ENTITY, self._delete_callback
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.values.values_id}_value_added",
                self._value_added,
            )
        )

    @property
    def device_info(self):
        """Return device information for the device registry."""
        node = self.values.primary.node
        node_instance = self.values.primary.instance
        dev_id = create_device_id(node, self.values.primary.instance)
        node_firmware = node.get_value(
            CommandClass.VERSION, ValueIndex.VERSION_APPLICATION
        )
        device_info = {
            "identifiers": {(DOMAIN, dev_id)},
            "name": create_device_name(node),
            "manufacturer": node.node_manufacturer_name,
            "model": node.node_product_name,
        }
        if node_firmware is not None:
            device_info["sw_version"] = node_firmware.value

        # device with multiple instances is split up into virtual devices for each instance
        if node_instance > 1:
            parent_dev_id = create_device_id(node)
            device_info["name"] += f" - Instance {node_instance}"
            device_info["via_device"] = (DOMAIN, parent_dev_id)
        return device_info

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {const.ATTR_NODE_ID: self.values.primary.node.node_id}

    @property
    def name(self):
        """Return the name of the entity."""
        node = self.values.primary.node
        return f"{create_device_name(node)}: {self.values.primary.label}"

    @property
    def unique_id(self):
        """Return the unique_id of the entity."""
        return self.values.values_id

    @property
    def available(self) -> bool:
        """Return entity availability."""
        # Use OZW Daemon status for availability.
        instance_status = self.values.primary.ozw_instance.get_status()
        return instance_status and instance_status.status in OZW_READY_STATES_VALUES

    @callback
    def _value_changed(self, value):
        """Call when a value from ZWaveDeviceEntityValues is changed.

        Should not be overridden by subclasses.
        """
        if value.value_id_key in (v.value_id_key for v in self.values if v):
            self.on_value_update()
            self.async_write_ha_state()

    @callback
    def _value_added(self):
        """Call when a value from ZWaveDeviceEntityValues is added.

        Should not be overridden by subclasses.
        """
        self.on_value_update()

    @callback
    def _instance_updated(self, new_status):
        """Call when the instance status changes.

        Should not be overridden by subclasses.
        """
        self.on_value_update()
        self.async_write_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def _delete_callback(self, values_id):
        """Remove this entity."""
        if not self.values:
            return  # race condition: delete already requested
        if values_id == self.values.values_id:
            await self.async_remove()


def create_device_name(node: OZWNode):
    """Generate sensible (short) default device name from a OZWNode."""
    # Prefer custom name set by OZWAdmin if present
    if node.node_name:
        return node.node_name
    # Prefer short devicename from metadata if present
    if node.meta_data and node.meta_data.get("Name"):
        return node.meta_data["Name"]
    # Fallback to productname or devicetype strings
    if node.node_product_name:
        return node.node_product_name
    if node.node_device_type_string:
        return node.node_device_type_string
    if node.node_specific_string:
        return node.node_specific_string
    # Last resort: use Node id (should never happen, but just in case)
    return f"Node {node.id}"


def create_device_id(node: OZWNode, node_instance: int = 1):
    """Generate unique device_id from a OZWNode."""
    ozw_instance = node.parent.id
    dev_id = f"{ozw_instance}.{node.node_id}.{node_instance}"
    return dev_id


def create_value_id(value: OZWValue):
    """Generate unique value_id from an OZWValue."""
    # [OZW_INSTANCE_ID]-[NODE_ID]-[VALUE_ID_KEY]
    return f"{value.node.parent.id}-{value.node.id}-{value.value_id_key}"


def set_config_parameter(
    manager, instance_id, node_id, parameter_index, new_value, node_instance_id=None
):
    """
    Set config parameter to a node.

    Returns success, payload, err_type, err_msg
    success: Whether method was successful
    payload: What was sent to the node
    err_type: If method was not successful, what type of error occurred
    err_msg: User friendly error message
    """
    instance = manager.get_instance(instance_id)
    if not instance:
        return False, None, ERR_NOT_FOUND, "OZW Instance not found"

    node = instance.get_node(node_id)
    if not node:
        return False, None, ERR_NOT_FOUND, "OZW Node not found"

    value = node.get_value(
        CommandClass.CONFIGURATION, parameter_index, node_instance_id
    )
    if not value:
        return (
            False,
            None,
            ERR_NOT_FOUND,
            "Configuration parameter for OZW Node Instance not found",
        )

    # Error message if new_value is an unexpected type
    type_err_msg = (
        f"Configuration parameter type {str(value.type)} does not "
        f"match the value type {str(type(new_value))}"
    )

    # Bool can be passed in as string or bool
    if value.type == ValueType.BOOL:
        if isinstance(new_value, bool):
            value.send_value(new_value)
            return True, new_value, None, None
        if isinstance(new_value, str):
            if new_value.lower() in ("true", "false"):
                payload = new_value.lower() == "true"
                value.send_value(payload)
                return True, payload, None, None

            return (
                False,
                None,
                ERR_NOT_SUPPORTED,
                "Configuration parameter requires true of false",
            )

        return False, None, ERR_NOT_SUPPORTED, type_err_msg

    # List value can be passed in as string or int
    if value.type == ValueType.LIST:
        try:
            new_value = int(new_value)
        except ValueError:
            pass
        if not isinstance(new_value, str) and not isinstance(new_value, int):
            return False, None, ERR_NOT_SUPPORTED, type_err_msg

        for option in value.value["List"]:
            if new_value not in (option["Label"], option["Value"]):
                continue
            payload = int(option["Value"])
            value.send_value(payload)
            return True, payload, None, None

        return (
            False,
            None,
            ERR_NOT_SUPPORTED,
            f"Value {new_value} not valid for parameter {parameter_index}",
        )

    if value.type == ValueType.STRING:
        if not isinstance(new_value, str):
            return False, None, ERR_NOT_SUPPORTED, type_err_msg
        value.send_value(new_value)
        return True, new_value, None, None

    if value.type in (ValueType.INT, ValueType.BYTE, ValueType.SHORT):
        try:
            new_value = int(new_value)
        except ValueError:
            return False, None, ERR_NOT_SUPPORTED, type_err_msg
        if new_value > value.max or new_value < value.min:
            return (
                False,
                None,
                ERR_NOT_SUPPORTED,
                (
                    f"Value {new_value} out of range for parameter "
                    f"{parameter_index} (Min: {value.min} Max: {value.max})"
                ),
            )
        value.send_value(new_value)
        return True, new_value, None, None

    return (
        False,
        None,
        ERR_NOT_SUPPORTED,
        f"Value type of {value.type} for parameter {parameter_index} not supported",
    )
