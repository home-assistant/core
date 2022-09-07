"""Starts a service to scan in intervals for new devices."""
from __future__ import annotations

from datetime import timedelta
import json
import logging
from typing import NamedTuple

from netdisco.discovery import NetworkDiscovery
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_discover, async_load_platform
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_zeroconf
import homeassistant.util.dt as dt_util

DOMAIN = "discovery"

SCAN_INTERVAL = timedelta(seconds=300)
SERVICE_APPLE_TV = "apple_tv"
SERVICE_DAIKIN = "daikin"
SERVICE_DLNA_DMR = "dlna_dmr"
SERVICE_ENIGMA2 = "enigma2"
SERVICE_HASS_IOS_APP = "hass_ios"
SERVICE_HASSIO = "hassio"
SERVICE_HEOS = "heos"
SERVICE_KONNECTED = "konnected"
SERVICE_MOBILE_APP = "hass_mobile_app"
SERVICE_NETGEAR = "netgear_router"
SERVICE_OCTOPRINT = "octoprint"
SERVICE_SABNZBD = "sabnzbd"
SERVICE_SAMSUNG_PRINTER = "samsung_printer"
SERVICE_TELLDUSLIVE = "tellstick"
SERVICE_YEELIGHT = "yeelight"
SERVICE_WEMO = "belkin_wemo"
SERVICE_XIAOMI_GW = "xiaomi_gw"

# These have custom protocols
CONFIG_ENTRY_HANDLERS = {
    SERVICE_TELLDUSLIVE: "tellduslive",
    "logitech_mediaserver": "squeezebox",
}


class ServiceDetails(NamedTuple):
    """Store service details."""

    component: str
    platform: str | None


# These have no config flows
SERVICE_HANDLERS = {
    SERVICE_ENIGMA2: ServiceDetails("media_player", "enigma2"),
    "yamaha": ServiceDetails("media_player", "yamaha"),
    "frontier_silicon": ServiceDetails("media_player", "frontier_silicon"),
    "openhome": ServiceDetails("media_player", "openhome"),
    "bluesound": ServiceDetails("media_player", "bluesound"),
}

OPTIONAL_SERVICE_HANDLERS: dict[str, tuple[str, str | None]] = {}

MIGRATED_SERVICE_HANDLERS = [
    SERVICE_APPLE_TV,
    "axis",
    "bose_soundtouch",
    "deconz",
    SERVICE_DAIKIN,
    "denonavr",
    SERVICE_DLNA_DMR,
    "esphome",
    "google_cast",
    SERVICE_HASS_IOS_APP,
    SERVICE_HASSIO,
    SERVICE_HEOS,
    "harmony",
    "homekit",
    "ikea_tradfri",
    "kodi",
    SERVICE_KONNECTED,
    SERVICE_MOBILE_APP,
    SERVICE_NETGEAR,
    SERVICE_OCTOPRINT,
    "philips_hue",
    SERVICE_SAMSUNG_PRINTER,
    "sonos",
    "songpal",
    SERVICE_WEMO,
    SERVICE_XIAOMI_GW,
    "volumio",
    SERVICE_YEELIGHT,
    SERVICE_SABNZBD,
    "nanoleaf_aurora",
    "lg_smart_device",
]

DEFAULT_ENABLED = (
    list(CONFIG_ENTRY_HANDLERS) + list(SERVICE_HANDLERS) + MIGRATED_SERVICE_HANDLERS
)
DEFAULT_DISABLED = list(OPTIONAL_SERVICE_HANDLERS) + MIGRATED_SERVICE_HANDLERS

CONF_IGNORE = "ignore"
CONF_ENABLE = "enable"

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional(CONF_IGNORE, default=[]): vol.All(
                    cv.ensure_list, [vol.In(DEFAULT_ENABLED)]
                ),
                vol.Optional(CONF_ENABLE, default=[]): vol.All(
                    cv.ensure_list, [vol.In(DEFAULT_DISABLED + DEFAULT_ENABLED)]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Start a discovery service."""

    logger = logging.getLogger(__name__)
    netdisco = NetworkDiscovery()
    already_discovered = set()

    if DOMAIN in config:
        # Platforms ignore by config
        ignored_platforms = config[DOMAIN][CONF_IGNORE]

        # Optional platforms enabled by config
        enabled_platforms = config[DOMAIN][CONF_ENABLE]
    else:
        ignored_platforms = []
        enabled_platforms = []

    for platform in enabled_platforms:
        if platform in DEFAULT_ENABLED:
            logger.warning(
                "Please remove %s from your discovery.enable configuration "
                "as it is now enabled by default",
                platform,
            )

    zeroconf_instance = await zeroconf.async_get_instance(hass)
    # Do not scan for types that have already been converted
    # as it will generate excess network traffic for questions
    # the zeroconf instance already knows the answers
    zeroconf_types = list(await async_get_zeroconf(hass))

    async def new_service_found(service, info):
        """Handle a new service if one is found."""
        if service in MIGRATED_SERVICE_HANDLERS:
            return

        if service in ignored_platforms:
            logger.info("Ignoring service: %s %s", service, info)
            return

        discovery_hash = json.dumps([service, info], sort_keys=True)
        if discovery_hash in already_discovered:
            logger.debug("Already discovered service %s %s.", service, info)
            return

        already_discovered.add(discovery_hash)

        if service in CONFIG_ENTRY_HANDLERS:
            discovery_flow.async_create_flow(
                hass,
                CONFIG_ENTRY_HANDLERS[service],
                context={"source": config_entries.SOURCE_DISCOVERY},
                data=info,
            )
            return

        service_details = SERVICE_HANDLERS.get(service)

        if not service_details and service in enabled_platforms:
            service_details = OPTIONAL_SERVICE_HANDLERS[service]

        # We do not know how to handle this service.
        if not service_details:
            logger.debug("Unknown service discovered: %s %s", service, info)
            return

        logger.info("Found new service: %s %s", service, info)

        if service_details.platform is None:
            await async_discover(hass, service, info, service_details.component, config)
        else:
            await async_load_platform(
                hass, service_details.component, service_details.platform, info, config
            )

    async def scan_devices(now):
        """Scan for devices."""
        try:
            results = await hass.async_add_executor_job(
                _discover, netdisco, zeroconf_instance, zeroconf_types
            )

            for result in results:
                hass.async_create_task(new_service_found(*result))
        except OSError:
            logger.error("Network is unreachable")

        async_track_point_in_utc_time(
            hass, scan_devices, dt_util.utcnow() + SCAN_INTERVAL
        )

    @callback
    def schedule_first(event):
        """Schedule the first discovery when Home Assistant starts up."""
        async_track_point_in_utc_time(hass, scan_devices, dt_util.utcnow())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, schedule_first)

    return True


def _discover(netdisco, zeroconf_instance, zeroconf_types):
    """Discover devices."""
    results = []
    try:
        netdisco.scan(
            zeroconf_instance=zeroconf_instance, suppress_mdns_types=zeroconf_types
        )

        for disc in netdisco.discover():
            for service in netdisco.get_info(disc):
                results.append((disc, service))

    finally:
        netdisco.stop()

    return results
