"""Sensor platform for SMTP integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SENDER, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMTP sensors based on a config entry."""
    entities: list[SensorEntity] = [
        SMTPStatusSensor(hass, entry),
        SMTPLastErrorSensor(hass, entry),
        SMTPLastSentSensor(hass, entry),
    ]

    async_add_entities(entities)

    # Store sensor references for updates
    hass.data[DOMAIN][entry.entry_id]["sensors"] = {
        "status": entities[0],
        "last_error": entities[1],
        "last_sent": entities[2],
    }


class SMTPBaseSensor(SensorEntity):
    """Base class for SMTP sensors."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry
        sender = entry.data.get(CONF_SENDER, "Email")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"SMTP ({sender})",
            manufacturer="SMTP",
            model="Email Service",
        )


class SMTPStatusSensor(SMTPBaseSensor):
    """Sensor showing SMTP connection status."""

    _attr_name = "Status"
    _attr_icon = "mdi:email-check"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the status sensor."""
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_native_value = "Connected"

    @callback
    def update_status(self, status: str) -> None:
        """Update the status."""
        self._attr_native_value = status
        if status == "Connected":
            self._attr_icon = "mdi:email-check"
        elif status == "Error":
            self._attr_icon = "mdi:email-remove"
        elif status == "Sending":
            self._attr_icon = "mdi:email-sync"
        else:
            self._attr_icon = "mdi:email"
        self.async_write_ha_state()


class SMTPLastErrorSensor(SMTPBaseSensor):
    """Sensor showing last SMTP error."""

    _attr_name = "Last error"
    _attr_icon = "mdi:email-alert"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the last error sensor."""
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_error"
        self._attr_native_value = None

    @callback
    def update_error(self, error: str | None) -> None:
        """Update the error."""
        self._attr_native_value = error
        self.async_write_ha_state()


class SMTPLastSentSensor(SMTPBaseSensor):
    """Sensor showing last email sent time."""

    _attr_name = "Last sent"
    _attr_icon = "mdi:email-fast"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the last sent sensor."""
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_sent"
        self._attr_native_value = "Never"

    @callback
    def update_sent(self) -> None:
        """Update the last sent time."""
        self._attr_native_value = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
        self.async_write_ha_state()
