"""Support for Tellstick covers."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import CoverEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    ATTR_DISCOVER_CONFIG,
    ATTR_DISCOVER_DEVICES,
    DATA_TELLSTICK,
    DEFAULT_SIGNAL_REPETITIONS,
    TellstickDevice,
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tellstick covers."""
    if discovery_info is None or discovery_info[ATTR_DISCOVER_DEVICES] is None:
        return

    signal_repetitions = discovery_info.get(
        ATTR_DISCOVER_CONFIG, DEFAULT_SIGNAL_REPETITIONS
    )

    add_entities(
        [
            TellstickCover(hass.data[DATA_TELLSTICK][tellcore_id], signal_repetitions)
            for tellcore_id in discovery_info[ATTR_DISCOVER_DEVICES]
        ],
        True,
    )


class TellstickCover(TellstickDevice, CoverEntity):
    """Representation of a Tellstick cover."""

    @property
    def is_closed(self) -> None:
        """Return the current position of the cover is not possible."""
        return None

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return True

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._tellcore_device.down()

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._tellcore_device.up()

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._tellcore_device.stop()

    def _parse_tellcore_data(self, tellcore_data):
        """Turn the value received from tellcore into something useful."""

    def _parse_ha_data(self, kwargs):
        """Turn the value from HA into something useful."""

    def _update_model(self, new_state, data):
        """Update the device entity state to match the arguments."""
