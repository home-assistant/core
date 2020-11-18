"""The SSDP integration."""
import asyncio
from datetime import timedelta
import itertools
import logging

import aiohttp
from defusedxml import ElementTree
from netdisco import ssdp, util

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.loader import async_get_ssdp

DOMAIN = "ssdp"
SCAN_INTERVAL = timedelta(seconds=60)

# Attributes for accessing info from SSDP response
ATTR_SSDP_LOCATION = "ssdp_location"
ATTR_SSDP_ST = "ssdp_st"
ATTR_SSDP_USN = "ssdp_usn"
ATTR_SSDP_EXT = "ssdp_ext"
ATTR_SSDP_SERVER = "ssdp_server"
# Attributes for accessing info from retrieved UPnP device description
ATTR_UPNP_DEVICE_TYPE = "deviceType"
ATTR_UPNP_FRIENDLY_NAME = "friendlyName"
ATTR_UPNP_MANUFACTURER = "manufacturer"
ATTR_UPNP_MANUFACTURER_URL = "manufacturerURL"
ATTR_UPNP_MODEL_DESCRIPTION = "modelDescription"
ATTR_UPNP_MODEL_NAME = "modelName"
ATTR_UPNP_MODEL_NUMBER = "modelNumber"
ATTR_UPNP_MODEL_URL = "modelURL"
ATTR_UPNP_SERIAL = "serialNumber"
ATTR_UPNP_UDN = "UDN"
ATTR_UPNP_UPC = "UPC"
ATTR_UPNP_PRESENTATION_URL = "presentationURL"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the SSDP integration."""

    async def initialize(_):
        scanner = Scanner(hass, await async_get_ssdp(hass))
        await scanner.async_scan(None)
        async_track_time_interval(hass, scanner.async_scan, SCAN_INTERVAL)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, initialize)

    return True


def _run_ssdp_scans():
    _LOGGER.debug("Scanning")
    # Run 3 times as packets can get lost
    return itertools.chain.from_iterable([ssdp.scan() for _ in range(3)])


class Scanner:
    """Class to manage SSDP scanning."""

    def __init__(self, hass, integration_matchers):
        """Initialize class."""
        self.hass = hass
        self.seen = set()
        self._integration_matchers = integration_matchers
        self._description_cache = {}

    async def async_scan(self, _):
        """Scan for new entries."""
        entries = await self.hass.async_add_executor_job(_run_ssdp_scans)

        await self._process_entries(entries)

        # We clear the cache after each run. We track discovered entries
        # so will never need a description twice.
        self._description_cache.clear()

    async def _process_entries(self, entries):
        """Process SSDP entries."""
        tasks = []

        for entry in entries:
            key = (entry.st, entry.location)

            if key in self.seen:
                continue

            self.seen.add(key)

            tasks.append(self._process_entry(entry))

        if not tasks:
            return

        to_load = [
            result for result in await asyncio.gather(*tasks) if result is not None
        ]

        if not to_load:
            return

        tasks = []

        for entry, info, domains in to_load:
            for domain in domains:
                _LOGGER.debug("Discovered %s at %s", domain, entry.location)
                tasks.append(
                    self.hass.config_entries.flow.async_init(
                        domain, context={"source": DOMAIN}, data=info
                    )
                )

        await asyncio.wait(tasks)

    async def _process_entry(self, entry):
        """Process a single entry."""

        info = {"st": entry.st}
        for key in "usn", "ext", "server":
            if key in entry.values:
                info[key] = entry.values[key]

        if entry.location:

            # Multiple entries usually share same location. Make sure
            # we fetch it only once.
            info_req = self._description_cache.get(entry.location)

            if info_req is None:
                info_req = self._description_cache[
                    entry.location
                ] = self.hass.async_create_task(self._fetch_description(entry.location))

            info.update(await info_req)

        domains = set()
        for domain, matchers in self._integration_matchers.items():
            for matcher in matchers:
                if all(info.get(k) == v for (k, v) in matcher.items()):
                    domains.add(domain)

        if domains:
            return (entry, info_from_entry(entry, info), domains)

        return None

    async def _fetch_description(self, xml_location):
        """Fetch an XML description."""
        session = self.hass.helpers.aiohttp_client.async_get_clientsession()
        try:
            resp = await session.get(xml_location, timeout=5)
            xml = await resp.text()

            # Samsung Smart TV sometimes returns an empty document the
            # first time. Retry once.
            if not xml:
                resp = await session.get(xml_location, timeout=5)
                xml = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error fetching %s: %s", xml_location, err)
            return {}

        try:
            tree = ElementTree.fromstring(xml)
        except ElementTree.ParseError as err:
            _LOGGER.debug("Error parsing %s: %s", xml_location, err)
            return {}

        return util.etree_to_dict(tree).get("root", {}).get("device", {})


def info_from_entry(entry, device_info):
    """Get info from an entry."""
    info = {
        ATTR_SSDP_LOCATION: entry.location,
        ATTR_SSDP_ST: entry.st,
    }
    if device_info:
        info.update(device_info)
        info.pop("st", None)
        if "usn" in info:
            info[ATTR_SSDP_USN] = info.pop("usn")
        if "ext" in info:
            info[ATTR_SSDP_EXT] = info.pop("ext")
        if "server" in info:
            info[ATTR_SSDP_SERVER] = info.pop("server")

    return info
