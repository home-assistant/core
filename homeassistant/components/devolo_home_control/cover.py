"""Platform for cover integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devolo_multi_level_switch import DevoloMultiLevelSwitchDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all cover devices and setup them via config entry."""
    entities = []

    for gateway in hass.data[DOMAIN][entry.entry_id]["gateways"]:
        for device in gateway.multi_level_switch_devices:
            for multi_level_switch in device.multi_level_switch_property:
                if multi_level_switch.startswith("devolo.Blinds"):
                    entities.append(
                        DevoloCoverDeviceEntity(
                            homecontrol=gateway,
                            device_instance=device,
                            element_uid=multi_level_switch,
                        )
                    )

    async_add_entities(entities)


class DevoloCoverDeviceEntity(DevoloMultiLevelSwitchDeviceEntity, CoverEntity):
    """Representation of a cover device within devolo Home Control."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )
    _attr_device_class = CoverDeviceClass.BLIND

    @property
    def current_cover_position(self) -> int:
        """Return the current position. 0 is closed. 100 is open."""
        return int(self._value)

    @property
    def is_closed(self) -> bool:
        """Return if the blind is closed or not."""
        return not bool(self._value)

    def open_cover(self, **kwargs: Any) -> None:
        """Open the blind."""
        self._multi_level_switch_property.set(100)

    def close_cover(self, **kwargs: Any) -> None:
        """Close the blind."""
        self._multi_level_switch_property.set(0)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Set the blind to the given position."""
        self._multi_level_switch_property.set(kwargs["position"])
