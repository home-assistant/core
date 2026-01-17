"""Support for Orvibo S20 smart switch."""

from typing import Any

from homeassistant.components.switch import SwitchEntity, timedelta
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OrviboConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OrviboConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the S20 switch entry."""
    async_add_entities([S20Switch(entry)], True)


class S20Switch(SwitchEntity):
    """Representation of an S20 switch."""

    _attr_name = None
    _attr_has_entity_name = True

    def __init__(self, entry: OrviboConfigEntry) -> None:
        """Initialize the S20 device."""
        self.data = entry.runtime_data
        self._state = self.data.switch.on
        self._attr_unique_id = entry.data[CONF_MAC]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_MAC])},
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    def update(self) -> None:
        """Update device state."""
        self._state = self.data.switch.on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.data.switch.on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self.data.switch.on = False
