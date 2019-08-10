"""The SSDP integration."""
import asyncio
from datetime import timedelta
import logging
from urllib.parse import urlparse
from xml.etree import ElementTree

import aiohttp
from netdisco import ssdp, util

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.generated.ssdp import SSDP

DOMAIN = "ssdp"
SCAN_INTERVAL = timedelta(seconds=60)

ATTR_HOST = "host"
ATTR_PORT = "port"
ATTR_SSDP_DESCRIPTION = "ssdp_description"
ATTR_ST = "ssdp_st"
ATTR_NAME = "name"
ATTR_MODEL_NAME = "model_name"
ATTR_MODEL_NUMBER = "model_number"
ATTR_SERIAL = "serial_number"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MANUFACTURERURL = "manufacturerURL"
ATTR_UDN = "udn"
ATTR_UPNP_DEVICE_TYPE = "upnp_device_type"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the SSDP integration."""

    async def initialize():
        scanner = Scanner(hass)
        await scanner.async_scan(None)
        async_track_time_interval(hass, scanner.async_scan, SCAN_INTERVAL)

    hass.loop.create_task(initialize())

    return True


class Scanner:
    """Class to manage SSDP scanning."""

    def __init__(self, hass):
        """Initialize class."""
        self.hass = hass
        self.seen = set()
        self._description_cache = {}

    async def async_scan(self, _):
        """Scan for new entries."""
        _LOGGER.debug("Scanning")
        # Run 3 times as packets can get lost
        for _ in range(3):
            entries = await self.hass.async_add_executor_job(ssdp.scan)
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
        domains = set(SSDP["st"].get(entry.st, []))

        xml_location = entry.location

        if not xml_location:
            if domains:
                return (entry, info_from_entry(entry, None), domains)
            return None

        # Multiple entries usally share same location. Make sure
        # we fetch it only once.
        info_req = self._description_cache.get(xml_location)

        if info_req is None:
            info_req = self._description_cache[
                xml_location
            ] = self.hass.async_create_task(self._fetch_description(xml_location))

        info = await info_req

        domains.update(SSDP["manufacturer"].get(info.get("manufacturer"), []))
        domains.update(SSDP["device_type"].get(info.get("deviceType"), []))

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
    """Get most important info from an entry."""
    url = urlparse(entry.location)
    info = {
        ATTR_HOST: url.hostname,
        ATTR_PORT: url.port,
        ATTR_SSDP_DESCRIPTION: entry.location,
        ATTR_ST: entry.st,
    }

    if device_info:
        info[ATTR_NAME] = device_info.get("friendlyName")
        info[ATTR_MODEL_NAME] = device_info.get("modelName")
        info[ATTR_MODEL_NUMBER] = device_info.get("modelNumber")
        info[ATTR_SERIAL] = device_info.get("serialNumber")
        info[ATTR_MANUFACTURER] = device_info.get("manufacturer")
        info[ATTR_MANUFACTURERURL] = device_info.get("manufacturerURL")
        info[ATTR_UDN] = device_info.get("UDN")
        info[ATTR_UPNP_DEVICE_TYPE] = device_info.get("deviceType")

    return info
