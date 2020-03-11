"""BleBox cover entity implementation."""
from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_SHUTTER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverDevice,
)

from . import CommonEntity, async_add_blebox


async def async_setup_platform(hass, config, async_add, discovery_info=None):
    """Set up BleBox platform."""
    return await async_add_blebox(BleBoxCoverEntity, "covers", hass, config, async_add)


async def async_setup_entry(hass, config_entry, async_add):
    """Set up a BleBox entry."""
    return await async_add_blebox(
        BleBoxCoverEntity, "covers", hass, config_entry.data, async_add,
    )


class BleBoxCoverEntity(CommonEntity, CoverDevice):
    """Representation of a BleBox cover feature."""

    @property
    def state(self):
        """Return the equivalent HA cover state."""
        states = {
            None: None,
            # TODO: use constants in lib instead of numbers
            0: STATE_CLOSING,  # moving down
            1: STATE_OPENING,  # moving up
            2: STATE_OPEN,  # manually stopped
            3: STATE_CLOSED,  # lower limit
            4: STATE_OPEN,  # upper limit / open
            # gateController
            5: STATE_OPEN,  # overload
            6: STATE_OPEN,  # motor failure
            # 7 is not used
            8: STATE_OPEN,  # safety stop
        }

        return states[self._feature.state]

    @property
    def device_class(self):
        """Return the device class."""
        types = {
            "shutter": DEVICE_CLASS_SHUTTER,
            "gatebox": DEVICE_CLASS_DOOR,
            "gate": DEVICE_CLASS_DOOR,
        }
        return types[self._feature.device_class]

    # TODO: does changing this at runtime really work as expected?
    @property
    def supported_features(self):
        """Return the supported cover features."""
        position = SUPPORT_SET_POSITION if self._feature.is_slider else 0
        stop = SUPPORT_STOP if self._feature.has_stop else 0

        return position | stop | SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def current_cover_position(self):
        """Return the current cover position."""
        position = self._feature.current
        return None if position is None else 100 - position

    @property
    def is_opening(self):
        """Return whether cover is opening."""
        return self._is_state(STATE_OPENING)

    @property
    def is_closing(self):
        """Return whether cover is closing."""
        return self._is_state(STATE_CLOSING)

    @property
    def is_closed(self):
        """Return whether cover is closed."""
        return self._is_state(STATE_CLOSED)

    async def async_open_cover(self, **kwargs):
        """Open the cover position."""
        await self._feature.async_open()

    async def async_close_cover(self, **kwargs):
        """Close the cover position."""
        await self._feature.async_close()

    async def async_set_cover_position(self, **kwargs):
        """Set the cover position."""
        position = kwargs[ATTR_POSITION]
        if position is not None:
            await self._feature.async_set_position(100 - position)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._feature.async_stop()

    def _is_state(self, state_name):
        value = self.state
        return None if value is None else value == state_name
