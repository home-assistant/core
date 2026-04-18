"""Binary Sensor entities for the Bang & Olufsen integration."""

from __future__ import annotations

from mozart_api.models import BatteryState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeoConfigEntry
from .const import CONNECTION_STATUS, DOMAIN, WebsocketNotification
from .entity import BeoEntity
from .util import supports_battery


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BeoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Binary Sensor entities from config entry."""
    if await supports_battery(config_entry.runtime_data.client):
        async_add_entities(new_entities=[BeoBinarySensorBatteryCharging(config_entry)])


class BeoBinarySensorBatteryCharging(BinarySensorEntity, BeoEntity):
    """Battery charging Binary Sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_is_on = False

    def __init__(self, config_entry: BeoConfigEntry) -> None:
        """Init the battery charging Binary Sensor."""
        super().__init__(config_entry, config_entry.runtime_data.client)

        self._attr_unique_id = f"{self._unique_id}_charging"

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._unique_id}_{CONNECTION_STATUS}",
                self._async_update_connection_state,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._unique_id}_{WebsocketNotification.BATTERY}",
                self._update_battery_charging,
            )
        )

    async def _update_battery_charging(self, data: BatteryState) -> None:
        """Update battery charging."""
        self._attr_is_on = bool(data.is_charging)
        self.async_write_ha_state()
