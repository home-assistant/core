"""Tracks devices by sending a ICMP echo request (ping)."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import subprocess

from icmplib import async_multiping
import voluptuous as vol

from homeassistant import const, util
from homeassistant.components.device_tracker import (
    CONF_SCAN_INTERVAL,
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    SCAN_INTERVAL,
    AsyncSeeCallback,
    SourceType,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.async_ import gather_with_concurrency
from homeassistant.util.process import kill_subprocess

from .const import DOMAIN, ICMP_TIMEOUT, PING_ATTEMPTS_COUNT, PING_PRIVS, PING_TIMEOUT

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
CONF_PING_COUNT = "count"
CONCURRENT_PING_LIMIT = 6

PLATFORM_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(const.CONF_HOSTS): {cv.slug: cv.string},
        vol.Optional(CONF_PING_COUNT, default=1): cv.positive_int,
    }
)


class HostSubProcess:
    """Host object with ping detection."""

    def __init__(self, ip_address, dev_id, hass, config, privileged):
        """Initialize the Host pinger."""
        self.hass = hass
        self.ip_address = ip_address
        self.dev_id = dev_id
        self._count = config[CONF_PING_COUNT]
        self._ping_cmd = ["ping", "-n", "-q", "-c1", "-W1", ip_address]

    def ping(self):
        """Send an ICMP echo request and return True if success."""
        with subprocess.Popen(
            self._ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        ) as pinger:
            try:
                pinger.communicate(timeout=1 + PING_TIMEOUT)
                return pinger.returncode == 0
            except subprocess.TimeoutExpired:
                kill_subprocess(pinger)
                return False

            except subprocess.CalledProcessError:
                return False

    def update(self) -> bool:
        """Update device state by sending one or more ping messages."""
        failed = 0
        while failed < self._count:  # check more times if host is unreachable
            if self.ping():
                return True
            failed += 1

        _LOGGER.debug("No response from %s failed=%d", self.ip_address, failed)
        return False


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the Host objects and return the update function."""

    privileged = hass.data[DOMAIN][PING_PRIVS]
    ip_to_dev_id = {ip: dev_id for (dev_id, ip) in config[const.CONF_HOSTS].items()}
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
            for (dev_id, ip) in config[const.CONF_HOSTS].items()
        ]

        async def async_update(now):
            """Update all the hosts on every interval time."""
            results = await gather_with_concurrency(
                CONCURRENT_PING_LIMIT,
                *(hass.async_add_executor_job(host.update) for host in hosts),
            )
            await asyncio.gather(
                *(
                    async_see(dev_id=host.dev_id, source_type=SourceType.ROUTER)
                    for idx, host in enumerate(hosts)
                    if results[idx]
                )
            )

    else:

        async def async_update(now):
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

    async def _async_update_interval(now):
        try:
            await async_update(now)
        finally:
            if not hass.is_stopping:
                async_track_point_in_utc_time(
                    hass, _async_update_interval, util.dt.utcnow() + interval
                )

    await _async_update_interval(None)
    return True
