"""Representation of Z-Wave locks."""
import logging

from openzwavemqtt.const import CommandClass
import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockEntity
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity

ATTR_CODE_SLOT = "code_slot"
ATTR_USERCODE = "usercode"

SERVICE_SET_USERCODE = "set_usercode"
SERVICE_GET_USERCODE = "get_usercode"
SERVICE_CLEAR_USERCODE = "clear_usercode"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave lock from config entry."""

    @callback
    def async_add_lock(value):
        """Add Z-Wave Lock."""
        lock = ZWaveLock(value)

        async_add_entities([lock])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, f"{DOMAIN}_new_{LOCK_DOMAIN}", async_add_lock)
    )

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_USERCODE,
        {
            vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
            vol.Required(ATTR_USERCODE): cv.string,
        },
        "async_set_usercode",
    )

    platform.async_register_entity_service(
        SERVICE_CLEAR_USERCODE,
        {vol.Required(ATTR_CODE_SLOT): vol.Coerce(int)},
        "async_clear_usercode",
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

    @callback
    def async_set_usercode(self, code_slot, usercode):
        """Set the usercode to index X on the lock."""
        lock_node = self.values.primary.node.values()

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
                _LOGGER.debug("User code at slot %s set", code_slot)
                break

    @callback
    def async_clear_usercode(self, code_slot):
        """Clear usercode in slot X on the lock."""
        lock_node = self.values.primary.node.values()

        for value in lock_node:
            if (
                value.command_class == CommandClass.USER_CODE
                and value.label == "Remove User Code"
            ):
                value.send_value(code_slot)
                # Sending twice because the first time it doesn't take
                value.send_value(code_slot)
                _LOGGER.info("Usercode at slot %s is cleared", code_slot)
                break
