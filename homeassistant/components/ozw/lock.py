"""Representation of Z-Wave locks."""
import logging

import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockEntity
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_CODE_SLOT,
    ATTR_INSTANCE_ID,
    ATTR_NODE_ID,
    ATTR_USERCODE,
    DATA_UNSUBSCRIBE,
    DOMAIN,
    SERVICE_CLEAR_USERCODE,
    SERVICE_GET_USERCODE,
    SERVICE_SET_USERCODE,
)
from .entity import ZWaveDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave lock from config entry."""

    @callback
    def async_add_lock(value):
        """Add Z-Wave Lock."""
        lock = ZWaveLock(value)

        async_add_entities([lock])

    def set_usercode(service):
        """Set the usercode to index X on the lock."""
        # instance_id = service.data[ATTR_INSTANCE_ID]
        # node_id = service.data[ATTR_NODE_ID]
        # code_slot = service.data[ATTR_CODE_SLOT]
        # usercode = service.data[ATTR_USERCODE]

        # for value in lock_node.get_values(
        #     class_id= COMMAND_CLASS_USER_CODE
        # ).values():
        #     if value.index != code_slot:
        #         continue
        #     if len(str(usercode)) < 4:
        #         _LOGGER.error(
        #             "Invalid code provided: (%s) "
        #             "usercode must be at least 4 and at most"
        #             " %s digits",
        #             usercode,
        #             len(value.data),
        #         )
        #         break
        #     value.data = str(usercode)
        #     break

    def get_usercode(service):
        """Get a usercode at index X on the lock."""
        # instance_id = service.data[ATTR_INSTANCE_ID]
        # node_id = service.data[ATTR_NODE_ID]
        # code_slot = service.data[ATTR_CODE_SLOT]

        # for value in lock_node.get_values(
        #     class_id= COMMAND_CLASS_USER_CODE
        # ).values():
        #     if value.index != code_slot:
        #         continue
        #     _LOGGER.info("Usercode at slot %s is: %s", value.index, value.data)
        #     break

    def clear_usercode(service):
        """Set usercode to slot X on the lock."""
        # instance_id = service.data[ATTR_INSTANCE_ID]
        # node_id = service.data[ATTR_NODE_ID]
        # code_slot = service.data[ATTR_CODE_SLOT]
        # data = ""

        # for value in lock_node.get_values(
        #     class_id= COMMAND_CLASS_USER_CODE
        # ).values():
        #     if value.index != code_slot:
        #         continue
        #     for i in range(len(value.data)):
        #         data += "\0"
        #         i += 1
        #     _LOGGER.debug("Data to clear lock: %s", data)
        #     value.data = data
        #     _LOGGER.info("Usercode at slot %s is cleared", value.index)
        #     break

    hass.services.async_register(
        LOCK_DOMAIN,
        SERVICE_SET_USERCODE,
        set_usercode,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                vol.Required(ATTR_NODE_ID): vol.Coerce(int),
                vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
                vol.Required(ATTR_USERCODE): cv.string,
            }
        ),
    )

    hass.services.async_register(
        LOCK_DOMAIN,
        SERVICE_GET_USERCODE,
        get_usercode,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                vol.Required(ATTR_NODE_ID): vol.Coerce(int),
                vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
            }
        ),
    )

    hass.services.async_register(
        LOCK_DOMAIN,
        SERVICE_CLEAR_USERCODE,
        clear_usercode,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_INSTANCE_ID, default=1): vol.Coerce(int),
                vol.Required(ATTR_NODE_ID): vol.Coerce(int),
                vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
            }
        ),
    )

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, f"{DOMAIN}_new_{LOCK_DOMAIN}", async_add_lock)
    )


class ZWaveLock(ZWaveDeviceEntity, LockEntity):
    """Representation of a Z-Wave lock."""

    @property
    def is_locked(self):
        """Return a boolean for the state of the lock."""
        return bool(self.values.primary.value)

    async def async_lock(self, **kwargs):
        """Lock the lock."""
        self.values.primary.send_value(True)

    async def async_unlock(self, **kwargs):
        """Unlock the lock."""
        self.values.primary.send_value(False)
