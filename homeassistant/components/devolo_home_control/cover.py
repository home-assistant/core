"""Platform for cover integration."""
import logging

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
from .devolo_device import DevoloDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all cover devices and setup them via config entry."""
    entities = []

    for device in hass.data[DOMAIN]["homecontrol"].multi_level_switch_devices:
        for multi_level_switch in device.multi_level_switch_property:
            if multi_level_switch.startswith("devolo.Blinds"):
                entities.append(
                    DevoloCoverDeviceEntity(
                        homecontrol=hass.data[DOMAIN]["homecontrol"],
                        device_instance=device,
                        element_uid=multi_level_switch,
                    )
                )

    async_add_entities(entities, False)


class DevoloCoverDeviceEntity(DevoloDeviceEntity, CoverEntity):
    """Representation of a cover device within devolo Home Control."""

    def __init__(self, homecontrol, device_instance, element_uid):
        """Initialize a devolo blinds device."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
            name=device_instance.item_name,
            sync=self._sync,
        )

        self._multi_level_switch_property = device_instance.multi_level_switch_property.get(
            element_uid
        )

        self._position = self._multi_level_switch_property.value

    @property
    def current_cover_position(self):
        """Return the current position. 0 is closed. 100 is open."""
        return self._position

    @property
    def device_class(self):
        """Return the class of the device."""
        return DEVICE_CLASS_BLIND

    @property
    def is_closed(self):
        """Return if the blind is closed or not."""
        return not bool(self._position)

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

    def _sync(self, message=None):
        """Update the binary sensor state."""
        if message[0] == self._unique_id:
            self._position = message[1]
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("Not valid message received: %s", message)
        self.schedule_update_ha_state()
