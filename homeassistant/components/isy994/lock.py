"""Support for ISY994 locks."""
from typing import Callable

from homeassistant.components.lock import DOMAIN as LOCK, LockEntity
from homeassistant.const import STATE_LOCKED, STATE_UNKNOWN, STATE_UNLOCKED
from homeassistant.helpers.typing import ConfigType

from . import ISY994_NODES, ISY994_PROGRAMS
from .const import _LOGGER
from .entity import ISYNodeEntity, ISYProgramEntity

VALUE_TO_STATE = {0: STATE_UNLOCKED, 100: STATE_LOCKED}


def setup_platform(
    hass, config: ConfigType, add_entities: Callable[[list], None], discovery_info=None
):
    """Set up the ISY994 lock platform."""
    devices = []
    for node in hass.data[ISY994_NODES][LOCK]:
        devices.append(ISYLockEntity(node))

    for name, status, actions in hass.data[ISY994_PROGRAMS][LOCK]:
        devices.append(ISYLockProgramEntity(name, status, actions))

    add_entities(devices)


class ISYLockEntity(ISYNodeEntity, LockEntity):
    """Representation of an ISY994 lock device."""

    def __init__(self, node) -> None:
        """Initialize the ISY994 lock device."""
        super().__init__(node)
        self._conn = node.parent.parent.conn

    @property
    def is_locked(self) -> bool:
        """Get whether the lock is in locked state."""
        return self.state == STATE_LOCKED

    @property
    def state(self) -> str:
        """Get the state of the lock."""
        if self.is_unknown():
            return None
        return VALUE_TO_STATE.get(self.value, STATE_UNKNOWN)

    def lock(self, **kwargs) -> None:
        """Send the lock command to the ISY994 device."""
        # Hack until PyISY is updated
        req_url = self._conn.compileURL(["nodes", self.unique_id, "cmd", "SECMD", "1"])
        response = self._conn.request(req_url)

        if response is None:
            _LOGGER.error("Unable to lock device")

        self._node.update(0.5)

    def unlock(self, **kwargs) -> None:
        """Send the unlock command to the ISY994 device."""
        # Hack until PyISY is updated
        req_url = self._conn.compileURL(["nodes", self.unique_id, "cmd", "SECMD", "0"])
        response = self._conn.request(req_url)

        if response is None:
            _LOGGER.error("Unable to lock device")

        self._node.update(0.5)


class ISYLockProgramEntity(ISYProgramEntity, LockEntity):
    """Representation of a ISY lock program."""

    @property
    def is_locked(self) -> bool:
        """Return true if the device is locked."""
        return bool(self.value)

    @property
    def state(self) -> str:
        """Return the state of the lock."""
        return STATE_LOCKED if self.is_locked else STATE_UNLOCKED

    def lock(self, **kwargs) -> None:
        """Lock the device."""
        if not self._actions.runThen():
            _LOGGER.error("Unable to lock device")

    def unlock(self, **kwargs) -> None:
        """Unlock the device."""
        if not self._actions.runElse():
            _LOGGER.error("Unable to unlock device")
