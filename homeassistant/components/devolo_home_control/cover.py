"""Platform for cover integration."""
from __future__ import annotations

from typing import Any

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

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

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a climate entity within devolo Home Control."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._attr_device_class = CoverDeviceClass.BLIND
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )

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
