"""Tracks devices by sending a ICMP echo request (ping)."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
    SourceType,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_HOSTS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PingDomainData
from .const import CONF_IMPORTED_BY, CONF_PING_COUNT, DOMAIN
from .helpers import PingDataICMPLib, PingDataSubProcess

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOSTS): {cv.slug: cv.string},
        vol.Optional(CONF_PING_COUNT, default=1): cv.positive_int,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Legacy init: trigger import."""

    for dev_name, dev_host in config[CONF_HOSTS].items():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_IMPORTED_BY: "device_tracker",
                    CONF_NAME: dev_name,
                    CONF_HOST: dev_host,
                    CONF_PING_COUNT: config[CONF_PING_COUNT],
                },
            )
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Ping config entry."""

    data: PingDomainData = hass.data[DOMAIN]

    host: str = entry.options[CONF_HOST]
    count: int = int(entry.options[CONF_PING_COUNT])
    name: str = entry.options[CONF_NAME]
    privileged: bool | None = data.privileged
    ping_cls: type[PingDataSubProcess | PingDataICMPLib]
    if privileged is None:
        ping_cls = PingDataSubProcess
    else:
        ping_cls = PingDataICMPLib

    async_add_entities(
        [PingDeviceTracker(name, entry, ping_cls(hass, host, count, privileged))]
    )


class PingDeviceTracker(ScannerEntity):
    """Representation of a Ping device tracker."""

    ping: PingDataSubProcess | PingDataICMPLib

    def __init__(
        self,
        name: str,
        config_entry: ConfigEntry,
        ping_cls: PingDataSubProcess | PingDataICMPLib,
    ) -> None:
        """Initialize the Ping device tracker."""
        super().__init__()

        self._attr_name = name
        self.ping = ping_cls

        self._attr_unique_id = f"{config_entry.entry_id}"

        if CONF_IMPORTED_BY in config_entry.options:
            self._attr_entity_registry_enabled_default = bool(
                config_entry.options[CONF_IMPORTED_BY] == "device_tracker"
            )

    @property
    def source_type(self) -> SourceType:
        """Return the source type which is router."""
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        """Return true if ping returns is_alive."""
        return self.ping.is_alive

    async def async_update(self) -> None:
        """Update the sensor."""
        await self.ping.async_update()
