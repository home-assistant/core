"""Tracks the latency of a host by sending ICMP echo requests (ping)."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_ON
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PingDomainData
from .const import CONF_IMPORTED_BY, CONF_PING_COUNT, DEFAULT_PING_COUNT, DOMAIN
from .helpers import PingDataICMPLib, PingDataSubProcess

_LOGGER = logging.getLogger(__name__)

ATTR_ROUND_TRIP_TIME_AVG = "round_trip_time_avg"
ATTR_ROUND_TRIP_TIME_MAX = "round_trip_time_max"
ATTR_ROUND_TRIP_TIME_MDEV = "round_trip_time_mdev"
ATTR_ROUND_TRIP_TIME_MIN = "round_trip_time_min"

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
    """YAML init: import via config flow."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_IMPORTED_BY: "binary_sensor", **config},
        )
    )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Ping",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Ping config entry."""

    data: PingDomainData = hass.data[DOMAIN]

    host: str = entry.options[CONF_HOST]
    count: int = int(entry.options[CONF_PING_COUNT])
    ping_cls: type[PingDataSubProcess | PingDataICMPLib]
    if data.privileged is None:
        ping_cls = PingDataSubProcess
    else:
        ping_cls = PingDataICMPLib

    async_add_entities(
        [PingBinarySensor(entry, ping_cls(hass, host, count, data.privileged))]
    )


class PingBinarySensor(RestoreEntity, BinarySensorEntity):
    """Representation of a Ping Binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_available = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        ping_cls: PingDataSubProcess | PingDataICMPLib,
    ) -> None:
        """Initialize the Ping Binary sensor."""
        self._attr_name = config_entry.title
        self._attr_unique_id = config_entry.entry_id

        # if this was imported just enable it when it was enabled before
        if CONF_IMPORTED_BY in config_entry.data:
            self._attr_entity_registry_enabled_default = bool(
                config_entry.data[CONF_IMPORTED_BY] == "binary_sensor"
            )

        self._ping = ping_cls

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._ping.is_alive

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the ICMP checo request."""
        if self._ping.data is None:
            return None
        return {
            ATTR_ROUND_TRIP_TIME_AVG: self._ping.data["avg"],
            ATTR_ROUND_TRIP_TIME_MAX: self._ping.data["max"],
            ATTR_ROUND_TRIP_TIME_MDEV: self._ping.data["mdev"],
            ATTR_ROUND_TRIP_TIME_MIN: self._ping.data["min"],
        }

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
