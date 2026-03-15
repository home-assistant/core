"""Support for Lutron Caseta sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LutronCasetaEntity
from .models import LutronCasetaConfigEntry

BATTERY_REFRESH_INTERVAL = timedelta(days=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronCasetaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta sensor platform."""
    data = config_entry.runtime_data
    bridge = data.bridge
    async_add_entities(
        (
            LutronCasetaBatterySensor(device, data)
            for device in bridge.get_devices_by_domain(COVER_DOMAIN)
        ),
        update_before_add=True,
    )


class LutronCasetaBatterySensor(LutronCasetaEntity, SensorEntity):
    """Representation of a Lutron Caseta shade battery sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, device: dict[str, Any], data) -> None:
        """Initialize the battery sensor."""
        super().__init__(device, data)
        self._attr_name = "Battery"
        self._attr_native_value: str | None = None

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the battery sensor."""
        return f"{super().unique_id}_battery"

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Schedule periodic refreshes without bridge subscriptions."""
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_schedule_refresh,
                BATTERY_REFRESH_INTERVAL,
            )
        )

    async def _async_schedule_refresh(self, _now) -> None:
        """Refresh the battery sensor on a long interval."""
        await self.async_update_ha_state(True)

    async def async_update(self) -> None:
        """Fetch the latest battery status from the bridge."""
        self._attr_native_value = await self._smartbridge.get_battery_status(
            self.device_id
        )
