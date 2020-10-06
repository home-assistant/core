"""Methods and classes related to executing Z-Wave commands and publishing these to hass."""
import logging

from openzwavemqtt.const import ATTR_LABEL, ATTR_POSITION, ATTR_VALUE
from openzwavemqtt.util.node import get_node_from_manager, set_config_parameter
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
            const.SERVICE_CANCEL_COMMAND,
            self.async_cancel_command,
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
                        vol.All(
                            cv.ensure_list,
                            [
                                vol.All(
                                    {
                                        vol.Exclusive(ATTR_LABEL, "bit"): cv.string,
                                        vol.Exclusive(ATTR_POSITION, "bit"): vol.Coerce(
                                            int
                                        ),
                                        vol.Required(ATTR_VALUE): bool,
                                    },
                                    cv.has_at_least_one_key(ATTR_LABEL, ATTR_POSITION),
                                )
                            ],
                        ),
                        vol.Coerce(int),
                        bool,
                        cv.string,
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

        # These function calls may raise an exception but that's ok because
        # the exception will show in the UI to the user
        node = get_node_from_manager(self._manager, instance_id, node_id)
        payload = set_config_parameter(node, param, selection)

        _LOGGER.info(
            "Setting configuration parameter %s on Node %s with value %s",
            param,
            node_id,
            payload,
        )

    @callback
    def async_add_node(self, service):
        """Enter inclusion mode on the controller."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        secure = service.data[const.ATTR_SECURE]
        instance = self._manager.get_instance(instance_id)
        if instance is None:
            raise ValueError(f"No OpenZWave Instance with ID {instance_id}")
        instance.add_node(secure)

    @callback
    def async_remove_node(self, service):
        """Enter exclusion mode on the controller."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        instance = self._manager.get_instance(instance_id)
        if instance is None:
            raise ValueError(f"No OpenZWave Instance with ID {instance_id}")
        instance.remove_node()

    @callback
    def async_cancel_command(self, service):
        """Tell the controller to cancel an add or remove command."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        instance = self._manager.get_instance(instance_id)
        if instance is None:
            raise ValueError(f"No OpenZWave Instance with ID {instance_id}")
        instance.cancel_controller_command()
