"""Methods and classes related to executing Z-Wave commands and publishing these to hass."""
import logging

from openzwavemqtt.const import CommandClass
import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
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
            LOCK_DOMAIN,
            const.SERVICE_SET_USERCODE,
            self.set_usercode,
            schema=vol.Schema(
                {
                    vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
                    vol.Required(const.ATTR_CODE_SLOT): vol.Coerce(int),
                    vol.Required(const.ATTR_USERCODE): cv.string,
                }
            ),
        )

        self._hass.services.async_register(
            LOCK_DOMAIN,
            const.SERVICE_GET_USERCODE,
            self.get_usercode,
            schema=vol.Schema(
                {
                    vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
                    vol.Required(const.ATTR_CODE_SLOT): vol.Coerce(int),
                }
            ),
        )

        self._hass.services.async_register(
            LOCK_DOMAIN,
            const.SERVICE_CLEAR_USERCODE,
            self.clear_usercode,
            schema=vol.Schema(
                {
                    vol.Optional(const.ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
                    vol.Required(const.ATTR_CODE_SLOT): vol.Coerce(int),
                }
            ),
        )

    def set_usercode(self, service):
        """Set the usercode to index X on the lock."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        node_id = service.data[const.ATTR_NODE_ID]
        code_slot = service.data[const.ATTR_CODE_SLOT]
        usercode = service.data[const.ATTR_USERCODE]

        lock_node = self._manager.get_instance(instance_id).get_node(node_id).values()

        for value in lock_node:
            if (
                value.command_class == CommandClass.USER_CODE
                and value.index == code_slot
            ):
                if len(str(usercode)) < 4:
                    _LOGGER.error(
                        "Invalid code provided: (%s) user code must be at least 4 digits",
                        usercode,
                    )
                    break
                value.send_value(usercode)
                break

    def get_usercode(self, service):
        """Get a usercode at index X on the lock."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        node_id = service.data[const.ATTR_NODE_ID]
        code_slot = service.data[const.ATTR_CODE_SLOT]

        lock_node = self._manager.get_instance(instance_id).get_node(node_id).values()

        for value in lock_node:
            if (
                value.command_class == CommandClass.USER_CODE
                and value.index == code_slot
            ):
                _LOGGER.info("User code at slot %s is: %s", code_slot, value.value)
                break

    def clear_usercode(self, service):
        """Set usercode to slot X on the lock."""
        instance_id = service.data[const.ATTR_INSTANCE_ID]
        node_id = service.data[const.ATTR_NODE_ID]
        code_slot = service.data[const.ATTR_CODE_SLOT]

        lock_node = self._manager.get_instance(instance_id).get_node(node_id).values()

        for value in lock_node:
            if (
                value.command_class == CommandClass.USER_CODE
                and value.label == "Remove User Code"
            ):
                value.send_value(code_slot)
                value.send_value(code_slot)
                _LOGGER.info("Usercode at slot %s is cleared", code_slot)
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
