"""Tracks the latency of a host by sending ICMP echo requests (ping)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PingDomainData
from .const import CONF_IMPORTED_BY, CONF_PING_COUNT, DEFAULT_PING_COUNT, DOMAIN
from .ping import PingDataICMPLib, PingDataSubProcess

ATTR_ROUND_TRIP_TIME_AVG = "round_trip_time_avg"
ATTR_ROUND_TRIP_TIME_MAX = "round_trip_time_max"
ATTR_ROUND_TRIP_TIME_MDEV = "round_trip_time_mdev"
ATTR_ROUND_TRIP_TIME_MIN = "round_trip_time_min"

DEFAULT_NAME = "Ping"

SCAN_INTERVAL = timedelta(minutes=5)
PARALLEL_UPDATES = 50

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PING_COUNT, default=DEFAULT_PING_COUNT): vol.Range(
            min=1, max=100
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Legacy init: Trigger the import config flow."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_IMPORTED_BY: "binary_sensor", **config},
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Ping config entry."""

    data: PingDomainData = hass.data[DOMAIN]

    host: str = entry.options[CONF_HOST]
    count: int = int(entry.options[CONF_PING_COUNT])
    name: str = entry.options.get(CONF_NAME, f"{DEFAULT_NAME} {host}")
    privileged: bool | None = data.privileged
    ping_cls: type[PingDataSubProcess | PingDataICMPLib]
    if privileged is None:
        ping_cls = PingDataSubProcess
    else:
        ping_cls = PingDataICMPLib

    async_add_entities(
        [PingBinarySensor(name, entry, ping_cls(hass, host, count, privileged))]
    )


class PingBinarySensor(RestoreEntity, BinarySensorEntity):
    """Representation of a Ping Binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    config_entry: ConfigEntry

    def __init__(
        self,
        name: str,
        config_entry: ConfigEntry,
        ping: PingDataSubProcess | PingDataICMPLib,
    ) -> None:
        """Initialize the Ping Binary sensor."""
        self._attr_available = False
        self._attr_name = name
        self._ping = ping
        self._attr_unique_id = f"{config_entry.entry_id}_binary_sensor"
        self.config_entry = config_entry

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._ping.is_alive

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the ICMP echo request."""
        if self._ping.data is None:
            return None
        return {
            ATTR_ROUND_TRIP_TIME_AVG: self._ping.data["avg"],
            ATTR_ROUND_TRIP_TIME_MAX: self._ping.data["max"],
            ATTR_ROUND_TRIP_TIME_MDEV: self._ping.data["mdev"],
            ATTR_ROUND_TRIP_TIME_MIN: self._ping.data["min"],
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        if CONF_IMPORTED_BY in self.config_entry.options:
            return bool(self.config_entry.options[CONF_IMPORTED_BY] == "binary_sensor")
        return True

    async def async_update(self) -> None:
        """Get the latest data."""
        await self._ping.async_update()
        self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """Restore previous state on restart to avoid blocking startup."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_available = True

        if last_state is None or last_state.state != STATE_ON:
            self._ping.data = None
            return

        attributes = last_state.attributes
        self._ping.is_alive = True
        self._ping.data = {
            "min": attributes[ATTR_ROUND_TRIP_TIME_MIN],
            "max": attributes[ATTR_ROUND_TRIP_TIME_MAX],
            "avg": attributes[ATTR_ROUND_TRIP_TIME_AVG],
            "mdev": attributes[ATTR_ROUND_TRIP_TIME_MDEV],
        }
