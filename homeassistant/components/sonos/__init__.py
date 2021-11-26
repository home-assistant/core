"""Support to embed Sonos."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import datetime
from enum import Enum
from functools import partial
import logging
import socket
from urllib.parse import urlparse

from soco import events_asyncio
import soco.config as soco_config
from soco.core import SoCo
from soco.exceptions import NotSupportedException, SoCoException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOSTS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .alarms import SonosAlarms
from .const import (
    AVAILABILITY_CHECK_INTERVAL,
    DATA_SONOS,
    DATA_SONOS_DISCOVERY_MANAGER,
    DISCOVERY_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SONOS_CHECK_ACTIVITY,
    SONOS_REBOOTED,
    SONOS_SPEAKER_ACTIVITY,
    UPNP_ST,
)
from .favorites import SonosFavorites
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)

CONF_ADVERTISE_ADDR = "advertise_addr"
CONF_INTERFACE_ADDR = "interface_addr"
DISCOVERY_IGNORED_MODELS = ["Sonos Boost"]


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                MP_DOMAIN: vol.All(
                    cv.deprecated(CONF_INTERFACE_ADDR),
                    vol.Schema(
                        {
                            vol.Optional(CONF_ADVERTISE_ADDR): cv.string,
                            vol.Optional(CONF_INTERFACE_ADDR): cv.string,
                            vol.Optional(CONF_HOSTS): vol.All(
                                cv.ensure_list_csv, [cv.string]
                            ),
                        }
                    ),
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class SoCoCreationSource(Enum):
    """Represent the creation source of a SoCo instance."""

    CONFIGURED = "configured"
    DISCOVERED = "discovered"
    REBOOTED = "rebooted"


class SonosData:
    """Storage class for platform global data."""

    def __init__(self) -> None:
        """Initialize the data."""
        # OrderedDict behavior used by SonosAlarms and SonosFavorites
        self.discovered: OrderedDict[str, SonosSpeaker] = OrderedDict()
        self.favorites: dict[str, SonosFavorites] = {}
        self.alarms: dict[str, SonosAlarms] = {}
        self.topology_condition = asyncio.Condition()
        self.hosts_heartbeat = None
        self.discovery_ignored: set[str] = set()
        self.discovery_known: set[str] = set()
        self.boot_counts: dict[str, int] = {}
        self.mdns_names: dict[str, str] = {}


async def async_setup(hass, config):
    """Set up the Sonos component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonos from a config entry."""
    soco_config.EVENTS_MODULE = events_asyncio

    if DATA_SONOS not in hass.data:
        hass.data[DATA_SONOS] = SonosData()

    data = hass.data[DATA_SONOS]
    config = hass.data[DOMAIN].get("media_player", {})
    hosts = config.get(CONF_HOSTS, [])
    _LOGGER.debug("Reached async_setup_entry, config=%s", config)

    if advertise_addr := config.get(CONF_ADVERTISE_ADDR):
        soco_config.EVENT_ADVERTISE_IP = advertise_addr

    if deprecated_address := config.get(CONF_INTERFACE_ADDR):
        _LOGGER.warning(
            "'%s' is deprecated, enable %s in the Network integration (https://www.home-assistant.io/integrations/network/)",
            CONF_INTERFACE_ADDR,
            deprecated_address,
        )

    manager = hass.data[DATA_SONOS_DISCOVERY_MANAGER] = SonosDiscoveryManager(
        hass, entry, data, hosts
    )
    hass.async_create_task(manager.setup_platforms_and_discovery())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Sonos config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await hass.data[DATA_SONOS_DISCOVERY_MANAGER].async_shutdown()
    hass.data.pop(DATA_SONOS)
    hass.data.pop(DATA_SONOS_DISCOVERY_MANAGER)
    return unload_ok


class SonosDiscoveryManager:
    """Manage sonos discovery."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, data: SonosData, hosts: list[str]
    ) -> None:
        """Init discovery manager."""
        self.hass = hass
        self.entry = entry
        self.data = data
        self.hosts = hosts
        self.discovery_lock = asyncio.Lock()

    async def async_shutdown(self):
        """Stop all running tasks."""
        await self._async_stop_event_listener()
        self._stop_manual_heartbeat()

    def _create_soco(self, ip_address: str, source: SoCoCreationSource) -> SoCo | None:
        """Create a soco instance and return if successful."""
        if ip_address in self.data.discovery_ignored:
            return None

        try:
            soco = SoCo(ip_address)
            # Ensure that the player is available and UID is cached
            uid = soco.uid
            _ = soco.volume
            return soco
        except NotSupportedException as exc:
            _LOGGER.debug("Device %s is not supported, ignoring: %s", uid, exc)
            self.data.discovery_ignored.add(ip_address)
        except (OSError, SoCoException) as ex:
            _LOGGER.warning(
                "Failed to connect to %s player '%s': %s", source.value, ip_address, ex
            )
        return None

    async def _async_stop_event_listener(self, event: Event | None = None) -> None:
        await asyncio.gather(
            *(speaker.async_offline() for speaker in self.data.discovered.values())
        )
        if events_asyncio.event_listener:
            await events_asyncio.event_listener.async_stop()

    def _stop_manual_heartbeat(self, event: Event | None = None) -> None:
        if self.data.hosts_heartbeat:
            self.data.hosts_heartbeat()
            self.data.hosts_heartbeat = None

    def _discovered_player(self, soco: SoCo) -> None:
        """Handle a (re)discovered player."""
        try:
            speaker_info = soco.get_speaker_info(True)
            _LOGGER.debug("Adding new speaker: %s", speaker_info)
            speaker = SonosSpeaker(self.hass, soco, speaker_info)
            self.data.discovered[soco.uid] = speaker
            for coordinator, coord_dict in (
                (SonosAlarms, self.data.alarms),
                (SonosFavorites, self.data.favorites),
            ):
                if soco.household_id not in coord_dict:
                    new_coordinator = coordinator(self.hass, soco.household_id)
                    new_coordinator.setup(soco)
                    coord_dict[soco.household_id] = new_coordinator
            speaker.setup(self.entry)
        except (OSError, SoCoException):
            _LOGGER.warning("Failed to add SonosSpeaker using %s", soco, exc_info=True)

    def _manual_hosts(self, now: datetime.datetime | None = None) -> None:
        """Players from network configuration."""
        for host in self.hosts:
            ip_addr = socket.gethostbyname(host)
            known_uid = next(
                (
                    uid
                    for uid, speaker in self.data.discovered.items()
                    if speaker.soco.ip_address == ip_addr
                ),
                None,
            )
            if not known_uid:
                soco = self._create_soco(ip_addr, SoCoCreationSource.CONFIGURED)
                if soco and soco.is_visible:
                    self._discovered_player(soco)

        self.data.hosts_heartbeat = self.hass.helpers.event.call_later(
            DISCOVERY_INTERVAL.total_seconds(), self._manual_hosts
        )

    def _discovered_ip(self, ip_address):
        soco = self._create_soco(ip_address, SoCoCreationSource.DISCOVERED)
        if soco and soco.is_visible:
            self._discovered_player(soco)

    async def _async_create_discovered_player(self, uid, discovered_ip, boot_seqnum):
        """Only create one player at a time."""
        async with self.discovery_lock:
            if uid not in self.data.discovered:
                await self.hass.async_add_executor_job(
                    self._discovered_ip, discovered_ip
                )
                return

            if boot_seqnum and boot_seqnum > self.data.boot_counts[uid]:
                self.data.boot_counts[uid] = boot_seqnum
                if soco := await self.hass.async_add_executor_job(
                    self._create_soco, discovered_ip, SoCoCreationSource.REBOOTED
                ):
                    async_dispatcher_send(self.hass, f"{SONOS_REBOOTED}-{uid}", soco)
            else:
                async_dispatcher_send(
                    self.hass, f"{SONOS_SPEAKER_ACTIVITY}-{uid}", "discovery"
                )

    async def _async_ssdp_discovered_player(self, info, change):
        if change == ssdp.SsdpChange.BYEBYE:
            return

        uid = info.get(ssdp.ATTR_UPNP_UDN)
        if not uid.startswith("uuid:RINCON_"):
            return

        uid = uid[5:]
        discovered_ip = urlparse(info[ssdp.ATTR_SSDP_LOCATION]).hostname
        boot_seqnum = info.get("X-RINCON-BOOTSEQ")
        self.async_discovered_player(
            "SSDP", info, discovered_ip, uid, boot_seqnum, info.get("modelName"), None
        )

    @callback
    def async_discovered_player(
        self, source, info, discovered_ip, uid, boot_seqnum, model, mdns_name
    ):
        """Handle discovery via ssdp or zeroconf."""
        if model in DISCOVERY_IGNORED_MODELS:
            _LOGGER.debug("Ignoring device: %s", info)
            return
        if boot_seqnum:
            boot_seqnum = int(boot_seqnum)
            self.data.boot_counts.setdefault(uid, boot_seqnum)
        if mdns_name:
            self.data.mdns_names[uid] = mdns_name

        if uid not in self.data.discovery_known:
            _LOGGER.debug("New %s discovery uid=%s: %s", source, uid, info)
            self.data.discovery_known.add(uid)
        asyncio.create_task(
            self._async_create_discovered_player(uid, discovered_ip, boot_seqnum)
        )

    async def setup_platforms_and_discovery(self):
        """Set up platforms and discovery."""
        await asyncio.gather(
            *(
                self.hass.config_entries.async_forward_entry_setup(self.entry, platform)
                for platform in PLATFORMS
            )
        )
        self.entry.async_on_unload(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._async_stop_event_listener
            )
        )
        _LOGGER.debug("Adding discovery job")
        if self.hosts:
            self.entry.async_on_unload(
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, self._stop_manual_heartbeat
                )
            )
            await self.hass.async_add_executor_job(self._manual_hosts)
            return

        self.entry.async_on_unload(
            await ssdp.async_register_callback(
                self.hass, self._async_ssdp_discovered_player, {"st": UPNP_ST}
            )
        )

        self.entry.async_on_unload(
            self.hass.helpers.event.async_track_time_interval(
                partial(
                    async_dispatcher_send,
                    self.hass,
                    SONOS_CHECK_ACTIVITY,
                ),
                AVAILABILITY_CHECK_INTERVAL,
            )
        )
