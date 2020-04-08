"""Device tracker helpers."""
import asyncio
from types import ModuleType
from typing import Any, Callable, Dict, Optional

import attr

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.setup import async_prepare_setup_platform
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    PLATFORM_TYPE_LEGACY,
    SCAN_INTERVAL,
    SOURCE_TYPE_ROUTER,
)


@attr.s
class DeviceTrackerPlatform:
    """Class to hold platform information."""

    LEGACY_SETUP = (
        "async_get_scanner",
        "get_scanner",
        "async_setup_scanner",
        "setup_scanner",
    )

    name = attr.ib(type=str)
    platform = attr.ib(type=ModuleType)
    config = attr.ib(type=Dict)

    @property
    def type(self):
        """Return platform type."""
        for methods, platform_type in ((self.LEGACY_SETUP, PLATFORM_TYPE_LEGACY),):
            for meth in methods:
                if hasattr(self.platform, meth):
                    return platform_type

        return None

    async def async_setup_legacy(self, hass, tracker, discovery_info=None):
        """Set up a legacy platform."""
        LOGGER.info("Setting up %s.%s", DOMAIN, self.type)
        try:
            scanner = None
            setup = None
            if hasattr(self.platform, "async_get_scanner"):
                scanner = await self.platform.async_get_scanner(
                    hass, {DOMAIN: self.config}
                )
            elif hasattr(self.platform, "get_scanner"):
                scanner = await hass.async_add_job(
                    self.platform.get_scanner, hass, {DOMAIN: self.config}
                )
            elif hasattr(self.platform, "async_setup_scanner"):
                setup = await self.platform.async_setup_scanner(
                    hass, self.config, tracker.async_see, discovery_info
                )
            elif hasattr(self.platform, "setup_scanner"):
                setup = await hass.async_add_job(
                    self.platform.setup_scanner,
                    hass,
                    self.config,
                    tracker.see,
                    discovery_info,
                )
            else:
                raise HomeAssistantError("Invalid legacy device_tracker platform.")

            if scanner:
                async_setup_scanner_platform(
                    hass, self.config, scanner, tracker.async_see, self.type
                )
                return

            if not setup:
                LOGGER.error("Error setting up platform %s", self.type)
                return

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Error setting up platform %s", self.type)


async def async_extract_config(hass, config):
    """Extract device tracker config and split between legacy and modern."""
    legacy = []

    for platform in await asyncio.gather(
        *(
            async_create_platform_type(hass, config, p_type, p_config)
            for p_type, p_config in config_per_platform(config, DOMAIN)
        )
    ):
        if platform is None:
            continue

        if platform.type == PLATFORM_TYPE_LEGACY:
            legacy.append(platform)
        else:
            raise ValueError(
                f"Unable to determine type for {platform.name}: {platform.type}"
            )

    return legacy


async def async_create_platform_type(
    hass, config, p_type, p_config
) -> Optional[DeviceTrackerPlatform]:
    """Determine type of platform."""
    platform = await async_prepare_setup_platform(hass, config, DOMAIN, p_type)

    if platform is None:
        return None

    return DeviceTrackerPlatform(p_type, platform, p_config)


@callback
def async_setup_scanner_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    scanner: Any,
    async_see_device: Callable,
    platform: str,
):
    """Set up the connect scanner-based platform to device tracker.

    This method must be run in the event loop.
    """
    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    update_lock = asyncio.Lock()
    scanner.hass = hass

    # Initial scan of each mac we also tell about host name for config
    seen: Any = set()

    async def async_device_tracker_scan(now: dt_util.dt.datetime):
        """Handle interval matches."""
        if update_lock.locked():
            LOGGER.warning(
                "Updating device list from %s took longer than the scheduled "
                "scan interval %s",
                platform,
                interval,
            )
            return

        async with update_lock:
            found_devices = await scanner.async_scan_devices()

        for mac in found_devices:
            if mac in seen:
                host_name = None
            else:
                host_name = await scanner.async_get_device_name(mac)
                seen.add(mac)

            try:
                extra_attributes = await scanner.async_get_extra_attributes(mac)
            except NotImplementedError:
                extra_attributes = dict()

            kwargs = {
                "mac": mac,
                "host_name": host_name,
                "source_type": SOURCE_TYPE_ROUTER,
                "attributes": {
                    "scanner": scanner.__class__.__name__,
                    **extra_attributes,
                },
            }

            zone_home = hass.states.get(hass.components.zone.ENTITY_ID_HOME)
            if zone_home:
                kwargs["gps"] = [
                    zone_home.attributes[ATTR_LATITUDE],
                    zone_home.attributes[ATTR_LONGITUDE],
                ]
                kwargs["gps_accuracy"] = 0

            hass.async_create_task(async_see_device(**kwargs))

    async_track_time_interval(hass, async_device_tracker_scan, interval)
    hass.async_create_task(async_device_tracker_scan(None))
