"""Demo platform that offers a fake Date/time entity."""
from __future__ import annotations

from datetime import date, datetime, time

from homeassistant.components.datetime import DateTimeEntity, DateTimeMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the demo Date/Time entity."""
    async_add_entities(
        [
            DemoDateTime(
                "datetime",
                "Date and Time",
                dt_util.now(),
                "mdi:calendar-clock",
                False,
            ),
            DemoDateTime(
                "date",
                "Date",
                dt_util.now().date(),
                "mdi:calendar",
                False,
                mode=DateTimeMode.DATE,
            ),
            DemoDateTime(
                "time",
                "Time",
                dt_util.now().time(),
                "mdi:clock",
                False,
                mode=DateTimeMode.TIME,
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoDateTime(DateTimeEntity):
    """Representation of a demo Date/time entity."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        state: datetime | date | time,
        icon: str,
        assumed_state: bool,
        mode: DateTimeMode = DateTimeMode.DATETIME,
    ) -> None:
        """Initialize the Demo Date/Time entity."""
        self._attr_assumed_state = assumed_state
        self._attr_icon = icon
        self._attr_mode = mode
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_native_value = state
        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, unique_id)
            },
            name=self.name,
        )

    async def async_set_datetime(self, dt_or_d_or_t: datetime | date | time) -> None:
        """Update the date/time."""
        self._attr_native_value = dt_or_d_or_t
        self.async_write_ha_state()
