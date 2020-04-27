"""Methods and classes related to executing Z-Wave commands and publishing these to hass."""
import logging

from openzwavemqtt.const import CommandClass, ValueType
import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import const

_LOGGER = logging.getLogger(__name__)


class ZWaveServices:
    """Class that holds our services ( Zwave Commands) that should be published to hass."""

    def __init__(self, hass, manager, data_nodes):
        """Initialize with both hass and ozwmanager objects."""
        self._hass = hass
        self._manager = manager
        self._data_nodes = data_nodes

    @callback
    def register(self):
        """Register all our services."""
        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_ADD_NODE,
            self.add_node,
            schema=vol.Schema(
                {
                    vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                    vol.Optional(const.ATTR_SECURE, default=False): vol.Coerce(bool),
                }
            ),
        )
        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_REMOVE_NODE,
            self.remove_node,
            schema=vol.Schema(
                {vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int)}
            ),
        )
        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_REMOVE_FAILED_NODE,
            self.remove_failed_node,
            schema=vol.Schema(
                {
                    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
                    vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                }
            ),
        )
        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_REPLACE_FAILED_NODE,
            self.replace_failed_node,
            schema=vol.Schema(
                {
                    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
                    vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                }
            ),
        )
        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_CANCEL_COMMAND,
            self.cancel_command,
            schema=vol.Schema(
                {vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int)}
            ),
        )
        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_SET_CONFIG_PARAMETER,
            self.set_config_parameter,
            schema=vol.Schema(
                {
                    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
                    vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Coerce(int),
                    vol.Required(const.ATTR_CONFIG_VALUE): vol.Any(
                        vol.Coerce(int), cv.string
                    ),
                    vol.Optional(const.ATTR_CONFIG_SIZE, default=2): vol.Coerce(int),
                    vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                }
            ),
        )

    @callback
    def add_node(self, service):
        """Enter inclusion mode on the controller."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        secure = service.data[const.ATTR_SECURE]
        instance = self._manager.get_instance(instance_id)
        instance.add_node(secure)

    @callback
    def remove_node(self, service):
        """Enter exclusion mode on the controller."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        instance = self._manager.get_instance(instance_id)
        instance.remove_node()

    @callback
    def remove_failed_node(self, service):
        """Remove a failed node from the controller."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        node_id = service.data[const.ATTR_NODE_ID]
        instance = self._manager.get_instance(instance_id)
        instance.remove_failed_node(node_id)

    @callback
    def replace_failed_node(self, service):
        """Replace a failed node from the controller with a new device."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        node_id = service.data[const.ATTR_NODE_ID]
        instance = self._manager.get_instance(instance_id)
        instance.replace_failed_node(node_id)

    @callback
    def cancel_command(self, service):
        """Cancel in Controller Commands that are in progress."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        instance = self._manager.get_instance(instance_id)
        instance.cancel_controller_command()

    @callback
    def set_config_parameter(self, service):
        """Set a config parameter to a node."""
        node_id = service.data[const.ATTR_NODE_ID]
        node = self._data_nodes[node_id]
        param = service.data.get(const.ATTR_CONFIG_PARAMETER)
        selection = service.data.get(const.ATTR_CONFIG_VALUE)
        # enumerate values until we find the param within configuration items
        for value in node.values():
            if value.index != param:
                continue
            if value.command_class != CommandClass.CONFIGURATION:
                continue
            _LOGGER.info(
                "Setting config parameter %s on Node %s with selection %s",
                param,
                node_id,
                selection,
            )
            # Bool value
            if value.type == ValueType.BOOL:
                return value.send_value(int(selection == "True"))
            # List value
            if value.type == ValueType.LIST:
                return value.send_value(str(selection))
            # Button
            if value.type == ValueType.BUTTON:
                value.send_value(True)
                value.send_value(False)
                return
            # Byte value
            value.send_value(int(selection))
            return

        # Parameter-index not found!
        _LOGGER.warning(
            "Unknown config parameter %s on Node %s with selection %s",
            param,
            node_id,
            selection,
        )
