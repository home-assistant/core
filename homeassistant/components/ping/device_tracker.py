"""Tracks devices by sending a ICMP echo request (ping)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from icmplib import async_multiping
import voluptuous as vol

from homeassistant.components.device_tracker import (
    CONF_SCAN_INTERVAL,
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
    SourceType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_HOSTS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import gather_with_limited_concurrency

from . import PingDomainData
from .const import CONF_PING_COUNT, DOMAIN, ICMP_TIMEOUT, PING_ATTEMPTS_COUNT
from .helpers import PingDataICMPLib, PingDataSubProcess

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
CONCURRENT_PING_LIMIT = 6
SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOSTS): {cv.slug: cv.string},
        vol.Optional(CONF_PING_COUNT, default=1): cv.positive_int,
    }
)


class HostSubProcess(PingDataSubProcess):
    """Host subclass using subprocess."""

    def __init__(
        self,
        ip_address: str,
        dev_id: str,
        hass: HomeAssistant,
        config: ConfigType,
        privileged: bool | None,
    ) -> None:
        """Initialize the subclass."""

        super().__init__(hass, ip_address, config[CONF_PING_COUNT], privileged)
        self.dev_id = dev_id

    async def async_is_alive(self) -> bool:
        """Overwrite subclass update method to return alive status."""
        await super().async_update()
        return self.is_alive


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the Host objects and return the update function."""

    data: PingDomainData = hass.data[DOMAIN]

    privileged = data.privileged
    ip_to_dev_id = {ip: dev_id for (dev_id, ip) in config[CONF_HOSTS].items()}
    interval = config.get(
        CONF_SCAN_INTERVAL,
        timedelta(seconds=len(ip_to_dev_id) * config[CONF_PING_COUNT]) + SCAN_INTERVAL,
    )
    _LOGGER.debug(
        "Started ping tracker with interval=%s on hosts: %s",
        interval,
        ",".join(ip_to_dev_id.keys()),
    )

    if privileged is None:
        hosts = [
            HostSubProcess(ip, dev_id, hass, config, privileged)
            for (dev_id, ip) in config[CONF_HOSTS].items()
        ]

        async def async_update(now: datetime) -> None:
            """Update all the hosts on every interval time."""
            results = await gather_with_limited_concurrency(
                CONCURRENT_PING_LIMIT,
                *(host.async_is_alive for host in hosts),
            )
            await asyncio.gather(
                *(
                    async_see(dev_id=host.dev_id, source_type=SourceType.ROUTER)
                    for idx, host in enumerate(hosts)
                    if results[idx]
                )
            )

    else:

        async def async_update(now: datetime) -> None:
            """Update all the hosts on every interval time."""
            responses = await async_multiping(
                list(ip_to_dev_id),
                count=PING_ATTEMPTS_COUNT,
                timeout=ICMP_TIMEOUT,
                privileged=privileged,
            )
            _LOGGER.debug("Multiping responses: %s", responses)
            await asyncio.gather(
                *(
                    async_see(dev_id=dev_id, source_type=SourceType.ROUTER)
                    for idx, dev_id in enumerate(ip_to_dev_id.values())
                    if responses[idx].is_alive
                )
            )

    async def _async_update_interval(now: datetime) -> None:
        try:
            await async_update(now)
        finally:
            if not hass.is_stopping:
                async_track_point_in_utc_time(
                    hass, _async_update_interval, now + interval
                )

    await _async_update_interval(dt_util.now())
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
        [PingDeviceTracker(name, ping_cls(hass, host, count, privileged))]
    )


class PingDeviceTracker(ScannerEntity):
    """Representation of a Ping device tracker."""

    ping: PingDataSubProcess | PingDataICMPLib

    def __init__(
        self,
        name: str,
        ping_cls: PingDataSubProcess | PingDataICMPLib,
    ) -> None:
        """Initialize the Ping device tracker."""
        super().__init__()

        self._attr_name = name
        self.ping = ping_cls

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self.ping.ip_address

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.ping.ip_address

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
