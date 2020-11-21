"""The SSDP integration."""
import asyncio
from datetime import timedelta
import itertools
import logging
from typing import Iterable, List, Mapping, Optional, Set, Tuple

import aiohttp
from defusedxml import ElementTree
from netdisco import ssdp, util
from netdisco.ssdp import UPNPEntry
import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.generated.ssdp import SSDP as SSDP_INTEGRATIONS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import async_get_ssdp

CONF_IGNORE = "ignore"

DOMAIN = "ssdp"
DOMAIN_CONFIG = "config"

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

SSDP_DEVICES = SSDP_INTEGRATIONS.keys()


_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_IGNORE, default=[]): vol.All(
                    cv.ensure_list, [vol.In(SSDP_DEVICES)]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the SSDP integration."""

    hass.data[DOMAIN] = {DOMAIN_CONFIG: config[DOMAIN]}

    async def initialize(_):
        scanner = Scanner(hass, await async_get_ssdp(hass))
        await scanner.async_scan(None)
        async_track_time_interval(hass, scanner.async_scan, SCAN_INTERVAL)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, initialize)

    return True


def _run_ssdp_scans() -> Iterable[UPNPEntry]:
    _LOGGER.debug("Scanning")
    # Run 3 times as packets can get lost
    return itertools.chain.from_iterable([ssdp.scan() for _ in range(3)])


class Scanner:
    """Class to manage SSDP scanning."""

    def __init__(self, hass: HomeAssistantType, integration_matchers: Mapping) -> None:
        """Initialize class."""
        self.hass = hass
        self.seen = set()
        self._integration_matchers: Mapping[str, Mapping] = integration_matchers
        self._description_cache: Mapping[str, Mapping] = {}

    async def async_scan(self, _) -> None:
        """Scan for new entries."""
        entries = await self.hass.async_add_executor_job(_run_ssdp_scans)

        await self._process_entries(entries)

        # We clear the cache after each run. We track discovered entries
        # so will never need a description twice.
        self._description_cache.clear()

    async def _process_entries(self, entries: Iterable[UPNPEntry]) -> None:
        """Process SSDP entries."""
        entries_to_process = []
        unseen_locations = set()

        for entry in entries:
            key = (entry.st, entry.location)

            if key in self.seen:
                continue

            self.seen.add(key)

            entries_to_process.append(entry)

            if (
                entry.location is not None
                and entry.location not in self._description_cache
            ):
                unseen_locations.add(entry.location)

        if not entries_to_process:
            return

        if unseen_locations:
            await self._fetch_descriptions(list(unseen_locations))

        tasks = []

        domains_to_ignore = self.hass.data[DOMAIN][DOMAIN_CONFIG][CONF_IGNORE]
        for entry in entries_to_process:
            info, domains = self._process_entry(entry)
            for domain in domains:
                if domain in domains_to_ignore:
                    _LOGGER.debug("Ignoring domain: %s at %s", domain, entry.location)
                    continue

                _LOGGER.debug("Discovered %s at %s", domain, entry.location)
                tasks.append(
                    self.hass.config_entries.flow.async_init(
                        domain, context={"source": DOMAIN}, data=info
                    )
                )

        if tasks:
            await asyncio.gather(*tasks)

    async def _fetch_descriptions(self, locations: List[str]) -> None:
        """Fetch descriptions from locations."""

        for idx, result in enumerate(
            await asyncio.gather(
                *[self._fetch_description(location) for location in locations],
                return_exceptions=True,
            )
        ):
            location = locations[idx]

            if isinstance(result, Exception):
                _LOGGER.exception(
                    "Failed to fetch ssdp data from: %s", location, exc_info=result
                )
                continue

            self._description_cache[location] = result

    def _process_entry(self, entry: UPNPEntry) -> Tuple[Optional[Mapping], Set[str]]:
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
                return (None, set())

            info.update(info_req)

        domains = set()
        for domain, matchers in self._integration_matchers.items():
            for matcher in matchers:
                if all(info.get(k) == v for (k, v) in matcher.items()):
                    domains.add(domain)

        if domains:
            return (info_from_entry(entry, info), domains)

        return (None, set())

    async def _fetch_description(self, xml_location: str) -> Mapping:
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


def info_from_entry(entry: UPNPEntry, device_info: Mapping) -> Mapping:
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
