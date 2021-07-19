"""Support for Fast.com internet speed testing sensor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DATA_RATE_MEGABITS_PER_SECOND
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_UPDATED, DOMAIN as FASTDOTCOM_DOMAIN

ICON = "mdi:speedometer"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fast.com sensor."""
    async_add_entities([SpeedtestSensor(hass.data[FASTDOTCOM_DOMAIN])])


class SpeedtestSensor(RestoreEntity, SensorEntity):
    """Implementation of a FAst.com sensor."""

    _attr_name = "Fast.com Download"
    _attr_unit_of_measurement = DATA_RATE_MEGABITS_PER_SECOND
    _attr_icon = ICON
    _attr_should_poll = False
    _attr_state = None

    def __init__(self, speedtest_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        self._speedtest_data = speedtest_data

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DATA_UPDATED, self._schedule_immediate_update
            )
        )

        state = await self.async_get_last_state()
        if not state:
            return
        self._attr_state = state.state

    def update(self) -> None:
        """Get the latest data and update the states."""
        data = self._speedtest_data.data  # type: ignore[attr-defined]
        if data is None:
            return
        self._attr_state = data["download"]

    @callback
    def _schedule_immediate_update(self) -> None:
        self.async_schedule_update_ha_state(True)
