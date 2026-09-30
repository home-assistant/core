"""Text entities for FMD integration."""

import logging
from typing import Any

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FMD text entities."""
    entities = [
        FmdWipePinText(hass, entry),
        FmdLockMessageText(hass, entry),
    ]

    async_add_entities(entities)

    # Store references for buttons to access
    entry.runtime_data.wipe_pin_text = entities[0]
    entry.runtime_data.lock_message_text = entities[1]


class FmdWipePinText(TextEntity):
    """Text entity for device wipe PIN.

    The PIN must be alphanumeric ASCII with no spaces.
    Note: Future FMD server versions may require 8+ character PINs.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.PASSWORD
    _attr_native_min = (
        0  # Allow empty initially, will be validated when wipe is triggered
    )
    _attr_native_max = 64

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the text entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_wipe_pin"
        self._attr_name = "Wipe: PIN"
        self._attr_native_value = entry.data.get("wipe_pin_native_value", "")
        self._attr_icon = "mdi:key-variant"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    @staticmethod
    def validate_pin(pin: str) -> tuple[bool, str]:
        """Validate wipe PIN meets requirements.

        Returns:
            tuple: (is_valid, error_message)
        """
        if not pin:
            return False, "PIN cannot be empty"

        if not pin.isalnum():
            return False, "PIN must be alphanumeric (letters and numbers only)"

        # Check if it's ASCII only
        if not all(ord(c) < 128 for c in pin):
            return False, "PIN must contain only ASCII characters"

        return True, ""

    async def async_set_value(self, value: str) -> None:
        """Update the PIN value with validation."""
        # Validate the PIN
        is_valid, error_msg = self.validate_pin(value)

        if not is_valid:
            _LOGGER.error("Invalid wipe PIN: %s", error_msg)
            raise ValueError(error_msg)

        # Warn if PIN is less than 8 characters
        if len(value) < 8:
            _LOGGER.warning(
                "Wipe PIN is less than 8 characters. "
                "Future FMD server versions may require 8+ character PINs."
            )

        _LOGGER.info("Wipe PIN updated (length: %d characters)", len(value))
        self._attr_native_value = value
        self.async_write_ha_state()

        # Persist to config entry (marked as sensitive)
        new_data = dict(self._entry.data)
        new_data["wipe_pin_native_value"] = value
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)


class FmdLockMessageText(TextEntity):
    """Text entity for optional lock screen message.

    The message will be displayed on the device's lock screen.
    Client automatically sanitizes dangerous characters.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 500  # Reasonable limit for lock screen message

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the text entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_lock_message"
        self._attr_name = "Lock: Message"
        self._attr_native_value = entry.data.get("lock_message_native_value", "")
        self._attr_icon = "mdi:message-text-lock"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    async def async_set_value(self, value: str) -> None:
        """Update the lock message value."""
        _LOGGER.info("Lock message updated (length: %d characters)", len(value))
        self._attr_native_value = value
        self.async_write_ha_state()

        # Persist to config entry
        new_data = dict(self._entry.data)
        new_data["lock_message_native_value"] = value
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)
