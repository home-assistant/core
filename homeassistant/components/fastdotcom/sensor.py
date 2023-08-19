"""Support for Fast.com internet speed testing sensor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import UnitOfDataRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_UPDATED, DOMAIN as FASTDOTCOM_DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Old legacy setup. Now initialize the import."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            FASTDOTCOM_DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={},
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fast.com sensor."""
    async_add_entities([SpeedtestSensor(hass.data[FASTDOTCOM_DOMAIN])])


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SpeedtestSensor(RestoreEntity, SensorEntity):
    """Implementation of a FAst.com sensor."""

    _attr_name = "Fast.com Download"
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:speedometer"
    _attr_should_poll = False

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

        if not (state := await self.async_get_last_state()):
            return
        self._attr_native_value = state.state

    def update(self) -> None:
        """Get the latest data and update the states."""
        if (data := self._speedtest_data.data) is None:  # type: ignore[attr-defined]
            return
        self._attr_native_value = data["download"]

    @callback
    def _schedule_immediate_update(self) -> None:
        self.async_schedule_update_ha_state(True)
