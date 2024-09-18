"""Support for Tellstick lights."""

from __future__ import annotations

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_DISCOVER_CONFIG,
    ATTR_DISCOVER_DEVICES,
    DATA_TELLSTICK,
    DEFAULT_SIGNAL_REPETITIONS,
)
from .entity import TellstickDevice


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tellstick lights."""
    if discovery_info is None or discovery_info[ATTR_DISCOVER_DEVICES] is None:
        return

    signal_repetitions = discovery_info.get(
        ATTR_DISCOVER_CONFIG, DEFAULT_SIGNAL_REPETITIONS
    )

    add_entities(
        [
            TellstickLight(hass.data[DATA_TELLSTICK][tellcore_id], signal_repetitions)
            for tellcore_id in discovery_info[ATTR_DISCOVER_DEVICES]
        ],
        True,
    )


class TellstickLight(TellstickDevice, LightEntity):
    """Representation of a Tellstick light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, tellcore_device, signal_repetitions):
        """Initialize the Tellstick light."""
        super().__init__(tellcore_device, signal_repetitions)

        self._brightness = 255

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    def _parse_ha_data(self, kwargs):
        """Turn the value from HA into something useful."""
        return kwargs.get(ATTR_BRIGHTNESS)

    def _parse_tellcore_data(self, tellcore_data):
        """Turn the value received from tellcore into something useful."""
        if tellcore_data:
            return int(tellcore_data)  # brightness
        return None

    def _update_model(self, new_state, data):
        """Update the device entity state to match the arguments."""
        if new_state:
            if (brightness := data) is not None:
                self._brightness = brightness

            # _brightness is not defined when called from super
            try:
                self._state = self._brightness > 0
            except AttributeError:
                self._state = True
        else:
            self._state = False

    def _send_device_command(self, requested_state, requested_data):
        """Let tellcore update the actual device to the requested state."""
        if requested_state:
            if requested_data is not None:
                self._brightness = int(requested_data)

            self._tellcore_device.dim(self._brightness)
        else:
            self._tellcore_device.turn_off()
