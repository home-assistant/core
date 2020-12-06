"""Support for Xiaomi Aqara locks."""
from homeassistant.components.lock import LockEntity
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later

from . import XiaomiDevice
from .const import DOMAIN, GATEWAYS_KEY

FINGER_KEY = "fing_verified"
PASSWORD_KEY = "psw_verified"
CARD_KEY = "card_verified"
VERIFIED_WRONG_KEY = "verified_wrong"

ATTR_VERIFIED_WRONG_TIMES = "verified_wrong_times"

UNLOCK_MAINTAIN_TIME = 5


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Xiaomi devices."""
    entities = []
    gateway = hass.data[DOMAIN][GATEWAYS_KEY][config_entry.entry_id]
    for device in gateway.devices["lock"]:
        model = device["model"]
        if model == "lock.aq1":
            entities.append(XiaomiAqaraLock(device, "Lock", gateway, config_entry))
    async_add_entities(entities)


class XiaomiAqaraLock(LockEntity, XiaomiDevice):
    """Representation of a XiaomiAqaraLock."""

    def __init__(self, device, name, xiaomi_hub, config_entry):
        """Initialize the XiaomiAqaraLock."""
        self._changed_by = 0
        self._verified_wrong_times = 0

        super().__init__(device, name, xiaomi_hub, config_entry)

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        if self._state is not None:
            return self._state == STATE_LOCKED

    @property
    def changed_by(self) -> int:
        """Last change triggered by."""
        return self._changed_by

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        attributes = {ATTR_VERIFIED_WRONG_TIMES: self._verified_wrong_times}
        return attributes

    @callback
    def clear_unlock_state(self, _):
        """Clear unlock state automatically."""
        self._state = STATE_LOCKED
        self.async_write_ha_state()

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        value = data.get(VERIFIED_WRONG_KEY)
        if value is not None:
            self._verified_wrong_times = int(value)
            return True

        for key in (FINGER_KEY, PASSWORD_KEY, CARD_KEY):
            value = data.get(key)
            if value is not None:
                self._changed_by = int(value)
                self._verified_wrong_times = 0
                self._state = STATE_UNLOCKED
                async_call_later(
                    self.hass, UNLOCK_MAINTAIN_TIME, self.clear_unlock_state
                )
                return True

        return False
