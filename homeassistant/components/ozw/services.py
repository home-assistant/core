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

    def __init__(self, hass, manager):
        """Initialize with both hass and ozwmanager objects."""
        self._hass = hass
        self._manager = manager

    @callback
    def async_register(self):
        """Register all our services."""
        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_ADD_NODE,
            self.async_add_node,
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
            self.async_remove_node,
            schema=vol.Schema(
                {vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int)}
            ),
        )

        self._hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_SET_CONFIG_PARAMETER,
            self.async_set_config_parameter,
            schema=vol.Schema(
                {
                    vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
                    vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Coerce(int),
                    vol.Required(const.ATTR_CONFIG_VALUE): vol.Any(
                        vol.Coerce(int), cv.string
                    ),
                }
            ),
        )

    @callback
    def async_set_config_parameter(self, service):
        """Set a config parameter to a node."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        node_id = service.data[const.ATTR_NODE_ID]
        param = service.data[const.ATTR_CONFIG_PARAMETER]
        selection = service.data[const.ATTR_CONFIG_VALUE]

        node = self._manager.get_instance(instance_id).get_node(node_id).values()

        for value in node:
            if (
                value.command_class == CommandClass.CONFIGURATION
                and value.index == param
            ):
                if value.type == ValueType.BOOL:
                    value.send_value(str(selection == "True"))
                    _LOGGER.info(
                        "Setting configuration parameter %s on Node %s with bool selection %s",
                        param,
                        node_id,
                        str(selection),
                    )
                    return
                if value.type == ValueType.LIST:
                    # accept either string from the list value OR the int value
                    if isinstance(selection, int):
                        if selection <= value.max:
                            value.send_value(int(selection))
                            _LOGGER.info(
                                "Setting configuration parameter %s on Node %s with list selection %s",
                                param,
                                node_id,
                                str(selection),
                            )
                            return
                        _LOGGER.error(
                            "Invalid value %s for parameter %s", str(selection), param,
                        )
                        break
                    # iterate list labels to get value
                    for selected in value.value["List"]:
                        if selected["Label"] == selection:
                            value.send_value(int(selected["Value"]))
                            _LOGGER.info(
                                "Setting configuration parameter %s on Node %s with list selection %s",
                                param,
                                node_id,
                                str(selection),
                            )
                            return
                        _LOGGER.error(
                            "Invalid value %s for parameter %s", str(selection), param,
                        )
                        break
                if value.type == ValueType.BUTTON:
                    # Unsupported at this time
                    _LOGGER.info("Button type not supported yet")
                    return
                if value.type == ValueType.INT:
                    if selection <= value.max:
                        value.send_value(int(selection))
                        _LOGGER.info(
                            "Setting configuration parameter %s on Node %s with selection %s",
                            param,
                            node_id,
                            selection,
                        )
                        return
                    _LOGGER.error(
                        "Invalid value %s for parameter %s, maximum value of %s",
                        str(selection),
                        param,
                        value.max,
                    )
                    break

    @callback
    def async_add_node(self, service):
        """Enter inclusion mode on the controller."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        secure = service.data[const.ATTR_SECURE]
        instance = self._manager.get_instance(instance_id)
        instance.add_node(secure)

    @callback
    def async_remove_node(self, service):
        """Enter exclusion mode on the controller."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        instance = self._manager.get_instance(instance_id)
        instance.remove_node()
