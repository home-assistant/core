"""Methods and classes related to executing Z-Wave commands and publishing these to hass."""
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import const
from .entity import set_config_parameter

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
                        bool, vol.Coerce(int), cv.string
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

        resp = set_config_parameter(
            self._manager, instance_id, node_id, param, selection
        )

        if not resp.success:
            _LOGGER.error(resp.err_msg, *resp.args)
            return

        _LOGGER.info(
            "Setting configuration parameter %s on Node %s with value %s",
            param,
            node_id,
            resp.payload,
        )

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
