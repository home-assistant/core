"""Tracks devices by sending a ICMP echo request (ping)."""
from datetime import timedelta
import logging
import subprocess
import sys

from icmplib import multiping
import voluptuous as vol

from homeassistant import const, util
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.device_tracker.const import (
    CONF_SCAN_INTERVAL,
    SCAN_INTERVAL,
    SOURCE_TYPE_ROUTER,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.process import kill_subprocess

from . import async_get_next_ping_id, can_use_icmp_lib_with_privilege
from .const import ICMP_TIMEOUT, PING_ATTEMPTS_COUNT, PING_TIMEOUT

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
CONF_PING_COUNT = "count"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
        if sys.platform == "win32":
            self._ping_cmd = ["ping", "-n", "1", "-w", "1000", ip_address]
        else:
            self._ping_cmd = ["ping", "-n", "-q", "-c1", "-W1", ip_address]

    def ping(self):
        """Send an ICMP echo request and return True if success."""
        pinger = subprocess.Popen(
            self._ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        try:
            pinger.communicate(timeout=1 + PING_TIMEOUT)
            return pinger.returncode == 0
        except subprocess.TimeoutExpired:
            kill_subprocess(pinger)
            return False

        except subprocess.CalledProcessError:
            return False

    def update(self, see):
        """Update device state by sending one or more ping messages."""
        failed = 0
        while failed < self._count:  # check more times if host is unreachable
            if self.ping():
                see(dev_id=self.dev_id, source_type=SOURCE_TYPE_ROUTER)
                return True
            failed += 1

        _LOGGER.debug("No response from %s failed=%d", self.ip_address, failed)


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Host objects and return the update function."""

    privileged = can_use_icmp_lib_with_privilege()
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

        def update(now):
            """Update all the hosts on every interval time."""
            for host in hosts:
                host.update(see)

    else:

        def update(now):
            """Update all the hosts on every interval time."""
            next_id = run_callback_threadsafe(
                hass.loop, async_get_next_ping_id, hass
            ).result()
            responses = multiping(
                ip_to_dev_id.keys(),
                count=PING_ATTEMPTS_COUNT,
                timeout=ICMP_TIMEOUT,
                privileged=privileged,
                id=next_id,
            )
            for host in responses:
                if host.is_alive:
                    see(
                        dev_id=ip_to_dev_id[host.address],
                        source_type=SOURCE_TYPE_ROUTER,
                    )

    def _update_interval(now):
        try:
            update(now)
        finally:
            hass.helpers.event.track_point_in_utc_time(
                _update_interval, util.dt.utcnow() + interval
            )

    _update_interval(None)
    return True
