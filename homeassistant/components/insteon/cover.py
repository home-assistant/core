"""Support for Insteon covers via PowerLinc Modem."""
import logging
import math

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)

from .insteon_entity import InsteonEntity

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Insteon platform."""
    if not discovery_info:
        return

    insteon_modem = hass.data["insteon"].get("modem")

    address = discovery_info["address"]
    device = insteon_modem.devices[address]
    state_key = discovery_info["state_key"]

    _LOGGER.debug(
        "Adding device %s entity %s to Cover platform",
        device.address.hex,
        device.states[state_key].name,
    )

    new_entity = InsteonCoverEntity(device, state_key)

    async_add_entities([new_entity])


class InsteonCoverEntity(InsteonEntity, CoverEntity):
    """A Class for an Insteon device."""

    @property
    def current_cover_position(self):
        """Return the current cover position."""
        return int(math.ceil(self._insteon_device_state.value * 100 / 255))

    @property
    def supported_features(self):
        """Return the supported features for this entity."""
        return SUPPORTED_FEATURES

    @property
    def is_closed(self):
        """Return the boolean response if the node is on."""
        return bool(self.current_cover_position)

    async def async_open_cover(self, **kwargs):
        """Open device."""
        self._insteon_device_state.open()

    async def async_close_cover(self, **kwargs):
        """Close device."""
        self._insteon_device_state.close()

    async def async_set_cover_position(self, **kwargs):
        """Set the cover position."""
        position = int(kwargs[ATTR_POSITION] * 255 / 100)
        if position == 0:
            self._insteon_device_state.close()
        else:
            self._insteon_device_state.set_position(position)
