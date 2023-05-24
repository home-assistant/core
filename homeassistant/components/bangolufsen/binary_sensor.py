"""Binary Sensor entities for the Bang & Olufsen integration."""
from __future__ import annotations

from mozart_api.models import BatteryState, WebsocketNotificationTag

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, BangOlufsenEntity, EntityEnum, WebSocketNotification


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Binary Sensor entities from config entry."""
    entities = []
    configuration = hass.data[DOMAIN][config_entry.unique_id]

    # Add BinarySensor entities
    for binary_sensor in configuration[EntityEnum.BINARY_SENSORS]:
        entities.append(binary_sensor)

    async_add_entities(new_entities=entities)


class BangOlufsenBinarySensor(BangOlufsenEntity, BinarySensorEntity):
    """Base Binary Sensor class."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the Binary Sensor."""
        super().__init__(entry)

        self._attr_is_on = False


class BangOlufsenBinarySensorBatteryCharging(BangOlufsenBinarySensor):
    """Battery charging Binary Sensor."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the battery charging Binary Sensor."""
        super().__init__(entry)

        self._attr_name = f"{self._name} Battery charging"
        self._attr_unique_id = f"{self._unique_id}-battery-charging"
        self._attr_icon = "mdi:battery-charging"
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()
        self._dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.BATTERY}",
                self._update_battery_charging,
            )
        )

    async def _update_battery_charging(self, data: BatteryState) -> None:
        """Update battery charging."""
        self._attr_is_on = data.is_charging
        self.async_write_ha_state()


class BangOlufsenBinarySensorProximity(BangOlufsenBinarySensor):
    """Proximity Binary Sensor."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the proximity Binary Sensor."""
        super().__init__(entry)

        self._attr_name = f"{self._name} proximity"
        self._attr_unique_id = f"{self._unique_id}-proximity"
        self._attr_icon = "mdi:account-question"

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()
        self._dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.PROXIMITY}",
                self._update_proximity,
            )
        )

    async def _update_proximity(self, data: WebsocketNotificationTag) -> None:
        """Update proximity."""
        if data.value == "proximityPresenceDetected":
            self._attr_is_on = True
        elif data.value == "proximityPresenceNotDetected":
            self._attr_is_on = False

        self.async_write_ha_state()
