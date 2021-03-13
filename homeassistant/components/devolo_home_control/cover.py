"""Platform for cover integration."""
from homeassistant.components.cover import (
    DEVICE_CLASS_BLIND,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .devolo_multi_level_switch import DevoloMultiLevelSwitchDeviceEntity


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
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

    async_add_entities(entities, False)


class DevoloCoverDeviceEntity(DevoloMultiLevelSwitchDeviceEntity, CoverEntity):
    """Representation of a cover device within devolo Home Control."""

    @property
    def current_cover_position(self):
        """Return the current position. 0 is closed. 100 is open."""
        return self._value

    @property
    def device_class(self):
        """Return the class of the device."""
        return DEVICE_CLASS_BLIND

    @property
    def is_closed(self):
        """Return if the blind is closed or not."""
        return not bool(self._value)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    def open_cover(self, **kwargs):
        """Open the blind."""
        self._multi_level_switch_property.set(100)

    def close_cover(self, **kwargs):
        """Close the blind."""
        self._multi_level_switch_property.set(0)

    def set_cover_position(self, **kwargs):
        """Set the blind to the given position."""
        self._multi_level_switch_property.set(kwargs["position"])
