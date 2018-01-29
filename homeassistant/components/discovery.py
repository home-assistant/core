"""
Starts a service to scan in intervals for new devices.

Will emit EVENT_PLATFORM_DISCOVERED whenever a new service has been discovered.

Knows which components handle certain types, will make sure they are
loaded before the EVENT_PLATFORM_DISCOVERED is fired.
"""
import asyncio
import json
from datetime import timedelta
import logging
import os

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_START
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.discovery import async_load_platform, async_discover
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['netdisco==1.2.4']

DOMAIN = 'discovery'

SCAN_INTERVAL = timedelta(seconds=300)
SERVICE_NETGEAR = 'netgear_router'
SERVICE_WEMO = 'belkin_wemo'
SERVICE_HASS_IOS_APP = 'hass_ios'
SERVICE_IKEA_TRADFRI = 'ikea_tradfri'
SERVICE_HASSIO = 'hassio'
SERVICE_AXIS = 'axis'
SERVICE_APPLE_TV = 'apple_tv'
SERVICE_WINK = 'wink'
SERVICE_XIAOMI_GW = 'xiaomi_gw'
SERVICE_TELLDUSLIVE = 'tellstick'
SERVICE_HUE = 'philips_hue'
SERVICE_DECONZ = 'deconz'
SERVICE_DAIKIN = 'daikin'

SERVICE_HANDLERS = {
    SERVICE_HASS_IOS_APP: ('ios', None),
    SERVICE_NETGEAR: ('device_tracker', None),
    SERVICE_WEMO: ('wemo', None),
    SERVICE_IKEA_TRADFRI: ('tradfri', None),
    SERVICE_HASSIO: ('hassio', None),
    SERVICE_AXIS: ('axis', None),
    SERVICE_APPLE_TV: ('apple_tv', None),
    SERVICE_WINK: ('wink', None),
    SERVICE_XIAOMI_GW: ('xiaomi_aqara', None),
    SERVICE_TELLDUSLIVE: ('tellduslive', None),
    SERVICE_HUE: ('hue', None),
    SERVICE_DECONZ: ('deconz', None),
    SERVICE_DAIKIN: ('daikin', None),
    'google_cast': ('media_player', 'cast'),
    'panasonic_viera': ('media_player', 'panasonic_viera'),
    'plex_mediaserver': ('media_player', 'plex'),
    'roku': ('media_player', 'roku'),
    'sonos': ('media_player', 'sonos'),
    'yamaha': ('media_player', 'yamaha'),
    'logitech_mediaserver': ('media_player', 'squeezebox'),
    'directv': ('media_player', 'directv'),
    'denonavr': ('media_player', 'denonavr'),
    'samsung_tv': ('media_player', 'samsungtv'),
    'yeelight': ('light', 'yeelight'),
    'frontier_silicon': ('media_player', 'frontier_silicon'),
    'openhome': ('media_player', 'openhome'),
    'harmony': ('remote', 'harmony'),
    'sabnzbd': ('sensor', 'sabnzbd'),
    'bose_soundtouch': ('media_player', 'soundtouch'),
    'bluesound': ('media_player', 'bluesound'),
}

CONF_IGNORE = 'ignore'

CONFIG_SCHEMA = vol.Schema({
    vol.Required(DOMAIN): vol.Schema({
        vol.Optional(CONF_IGNORE, default=[]):
            vol.All(cv.ensure_list, [vol.In(SERVICE_HANDLERS)])
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Start a discovery service."""
    from netdisco.discovery import NetworkDiscovery

    logger = logging.getLogger(__name__)
    netdisco = NetworkDiscovery()
    already_discovered = set()

    # Disable zeroconf logging, it spams
    logging.getLogger('zeroconf').setLevel(logging.CRITICAL)

    # Platforms ignore by config
    ignored_platforms = config[DOMAIN][CONF_IGNORE]

    @asyncio.coroutine
    def new_service_found(service, info):
        """Handle a new service if one is found."""
        if service in ignored_platforms:
            logger.info("Ignoring service: %s %s", service, info)
            return

        comp_plat = SERVICE_HANDLERS.get(service)

        # We do not know how to handle this service.
        if not comp_plat:
            logger.info("Unknown service discovered: %s %s", service, info)
            return

        discovery_hash = json.dumps([service, info], sort_keys=True)
        if discovery_hash in already_discovered:
            return

        already_discovered.add(discovery_hash)

        logger.info("Found new service: %s %s", service, info)

        component, platform = comp_plat

        if platform is None:
            yield from async_discover(hass, service, info, component, config)
        else:
            yield from async_load_platform(
                hass, component, platform, info, config)

    @asyncio.coroutine
    def scan_devices(now):
        """Scan for devices."""
        results = yield from hass.async_add_job(_discover, netdisco)

        for result in results:
            hass.async_add_job(new_service_found(*result))

        async_track_point_in_utc_time(hass, scan_devices,
                                      dt_util.utcnow() + SCAN_INTERVAL)

    @callback
    def schedule_first(event):
        """Schedule the first discovery when Home Assistant starts up."""
        async_track_point_in_utc_time(hass, scan_devices, dt_util.utcnow())

        # discovery local services
        if 'HASSIO' in os.environ:
            hass.async_add_job(new_service_found(SERVICE_HASSIO, {}))

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, schedule_first)

    return True


def _discover(netdisco):
    """Discover devices."""
    results = []
    try:
        netdisco.scan()

        for disc in netdisco.discover():
            for service in netdisco.get_info(disc):
                results.append((disc, service))
    finally:
        netdisco.stop()

    return results
