"""Support for Phone Modem button."""
from __future__ import annotations

from phone_modem import PhoneModem

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_KEY_API, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Modem Caller ID sensor."""
    api = hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]
    async_add_entities(
        [
            PhoneModemButton(
                api,
                entry.data[CONF_DEVICE],
                entry.entry_id,
            )
        ]
    )


class PhoneModemButton(ButtonEntity):
    """Implementation of USB modem caller ID button."""

    _attr_icon = "mdi:phone-hangup"
    _attr_translation_key = "phone_modem_reject"
    _attr_has_entity_name = True

    def __init__(self, api: PhoneModem, device: str, server_unique_id: str) -> None:
        """Initialize the button."""
        self.device = device
        self.api = api
        self._attr_unique_id = server_unique_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, server_unique_id)})

    async def async_press(self) -> None:
        """Press the button."""
        await self.api.reject_call(self.device)
