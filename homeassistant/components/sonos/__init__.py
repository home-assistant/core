"""Support to embed Sonos."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
import datetime
from functools import partial
import logging
import socket
from typing import TYPE_CHECKING, Any, Optional, cast
from urllib.parse import urlparse

from soco import events_asyncio
import soco.config as soco_config
from soco.core import SoCo
from soco.exceptions import SoCoException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOSTS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send
from homeassistant.helpers.event import async_track_time_interval, call_later
from homeassistant.helpers.typing import ConfigType

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
    SONOS_VANISHED,
    UPNP_ST,
)
from .exception import SonosUpdateError
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


@dataclass
class UnjoinData:
    """Class to track data necessary for unjoin coalescing."""

    speakers: list[SonosSpeaker]
    event: asyncio.Event = field(default_factory=asyncio.Event)


class SonosData:
    """Storage class for platform global data."""

    def __init__(self) -> None:
        """Initialize the data."""
        # OrderedDict behavior used by SonosAlarms and SonosFavorites
        self.discovered: OrderedDict[str, SonosSpeaker] = OrderedDict()
        self.favorites: dict[str, SonosFavorites] = {}
        self.alarms: dict[str, SonosAlarms] = {}
        self.topology_condition = asyncio.Condition()
        self.hosts_heartbeat: CALLBACK_TYPE | None = None
        self.discovery_known: set[str] = set()
        self.boot_counts: dict[str, int] = {}
        self.mdns_names: dict[str, str] = {}
        self.entity_id_mappings: dict[str, SonosSpeaker] = {}
        self.unjoin_data: dict[str, UnjoinData] = {}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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
    soco_config.REQUEST_TIMEOUT = 9.5

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
    await manager.setup_platforms_and_discovery()
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
        self.hosts = set(hosts)
        self.discovery_lock = asyncio.Lock()
        self._known_invisible: set[SoCo] = set()
        self._manual_config_required = bool(hosts)

    async def async_shutdown(self) -> None:
        """Stop all running tasks."""
        await self._async_stop_event_listener()
        self._stop_manual_heartbeat()

    def is_device_invisible(self, ip_address: str) -> bool:
        """Check if device at provided IP is known to be invisible."""
        return any(x for x in self._known_invisible if x.ip_address == ip_address)

    def _create_visible_speakers(self, ip_address: str) -> None:
        """Create all visible SonosSpeaker instances with the provided seed IP."""
        try:
            soco = SoCo(ip_address)
            visible_zones = soco.visible_zones
            self._known_invisible = soco.all_zones - visible_zones
        except (OSError, SoCoException) as ex:
            _LOGGER.warning(
                "Failed to request visible zones from %s: %s", ip_address, ex
            )
            return

        for zone in visible_zones:
            if zone.uid not in self.data.discovered:
                self._add_speaker(zone)

    async def _async_stop_event_listener(self, event: Event | None = None) -> None:
        for speaker in self.data.discovered.values():
            speaker.activity_stats.log_report()
            speaker.event_stats.log_report()
        if zgs := next(
            (
                speaker.soco.zone_group_state
                for speaker in self.data.discovered.values()
            ),
            None,
        ):
            _LOGGER.debug(
                "ZoneGroupState stats: (%s/%s) processed",
                zgs.processed_count,
                zgs.total_requests,
            )
        await asyncio.gather(
            *(speaker.async_offline() for speaker in self.data.discovered.values())
        )
        if events_asyncio.event_listener:
            await events_asyncio.event_listener.async_stop()

    def _stop_manual_heartbeat(self, event: Event | None = None) -> None:
        if self.data.hosts_heartbeat:
            self.data.hosts_heartbeat()
            self.data.hosts_heartbeat = None

    def _add_speaker(self, soco: SoCo) -> None:
        """Create and set up a new SonosSpeaker instance."""
        try:
            speaker_info = soco.get_speaker_info(True, timeout=7)
            if soco.uid not in self.data.boot_counts:
                self.data.boot_counts[soco.uid] = soco.boot_seqnum
            _LOGGER.debug("Adding new speaker: %s", speaker_info)
            speaker = SonosSpeaker(self.hass, soco, speaker_info)
            self.data.discovered[soco.uid] = speaker
            for coordinator, coord_dict in (
                (SonosAlarms, self.data.alarms),
                (SonosFavorites, self.data.favorites),
            ):
                if TYPE_CHECKING:
                    coord_dict = cast(dict[str, Any], coord_dict)
                if soco.household_id not in coord_dict:
                    new_coordinator = coordinator(self.hass, soco.household_id)
                    new_coordinator.setup(soco)
                    coord_dict[soco.household_id] = new_coordinator
            speaker.setup(self.entry)
        except (OSError, SoCoException):
            _LOGGER.warning("Failed to add SonosSpeaker using %s", soco, exc_info=True)

    def _poll_manual_hosts(self, now: datetime.datetime | None = None) -> None:
        """Add and maintain Sonos devices from a manual configuration."""
        for host in self.hosts:
            ip_addr = socket.gethostbyname(host)
            soco = SoCo(ip_addr)
            try:
                visible_zones = soco.visible_zones
            except OSError:
                _LOGGER.warning("Could not get visible Sonos devices from %s", ip_addr)
            else:
                if new_hosts := {
                    x.ip_address
                    for x in visible_zones
                    if x.ip_address not in self.hosts
                }:
                    _LOGGER.debug("Adding to manual hosts: %s", new_hosts)
                    self.hosts.update(new_hosts)
                dispatcher_send(
                    self.hass,
                    f"{SONOS_SPEAKER_ACTIVITY}-{soco.uid}",
                    "manual zone scan",
                )
                break

        for host in self.hosts.copy():
            ip_addr = socket.gethostbyname(host)
            if self.is_device_invisible(ip_addr):
                _LOGGER.debug("Discarding %s from manual hosts", ip_addr)
                self.hosts.discard(ip_addr)
                continue

            known_speaker = next(
                (
                    speaker
                    for speaker in self.data.discovered.values()
                    if speaker.soco.ip_address == ip_addr
                ),
                None,
            )
            if not known_speaker:
                self._create_visible_speakers(ip_addr)
            elif not known_speaker.available:
                try:
                    known_speaker.ping()
                except SonosUpdateError:
                    _LOGGER.debug(
                        "Manual poll to %s failed, keeping unavailable", ip_addr
                    )

        self.data.hosts_heartbeat = call_later(
            self.hass, DISCOVERY_INTERVAL.total_seconds(), self._poll_manual_hosts
        )

    async def _async_handle_discovery_message(
        self, uid: str, discovered_ip: str, boot_seqnum: int | None
    ) -> None:
        """Handle discovered player creation and activity."""
        async with self.discovery_lock:
            if not self.data.discovered:
                # Initial discovery, attempt to add all visible zones
                await self.hass.async_add_executor_job(
                    self._create_visible_speakers,
                    discovered_ip,
                )
            elif uid not in self.data.discovered:
                if self.is_device_invisible(discovered_ip):
                    return
                await self.hass.async_add_executor_job(
                    self._add_speaker, SoCo(discovered_ip)
                )
            elif boot_seqnum and boot_seqnum > self.data.boot_counts[uid]:
                self.data.boot_counts[uid] = boot_seqnum
                async_dispatcher_send(self.hass, f"{SONOS_REBOOTED}-{uid}")
            else:
                async_dispatcher_send(
                    self.hass, f"{SONOS_SPEAKER_ACTIVITY}-{uid}", "discovery"
                )

    async def _async_ssdp_discovered_player(
        self, info: ssdp.SsdpServiceInfo, change: ssdp.SsdpChange
    ) -> None:
        uid = info.upnp[ssdp.ATTR_UPNP_UDN]
        if not uid.startswith("uuid:RINCON_"):
            return
        uid = uid[5:]

        if change == ssdp.SsdpChange.BYEBYE:
            _LOGGER.debug(
                "ssdp:byebye received from %s", info.upnp.get("friendlyName", uid)
            )
            reason = info.ssdp_headers.get("X-RINCON-REASON", "ssdp:byebye")
            async_dispatcher_send(self.hass, f"{SONOS_VANISHED}-{uid}", reason)
            return

        self.async_discovered_player(
            "SSDP",
            info,
            cast(str, urlparse(info.ssdp_location).hostname),
            uid,
            info.ssdp_headers.get("X-RINCON-BOOTSEQ"),
            cast(str, info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME)),
            None,
        )

    @callback
    def async_discovered_player(
        self,
        source: str,
        info: ssdp.SsdpServiceInfo,
        discovered_ip: str,
        uid: str,
        boot_seqnum: str | int | None,
        model: str,
        mdns_name: str | None,
    ) -> None:
        """Handle discovery via ssdp or zeroconf."""
        if self._manual_config_required:
            _LOGGER.warning(
                "Automatic discovery is working, Sonos hosts in configuration.yaml are not needed"
            )
            self._manual_config_required = False
        if model in DISCOVERY_IGNORED_MODELS:
            _LOGGER.debug("Ignoring device: %s", info)
            return
        if self.is_device_invisible(discovered_ip):
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
            self._async_handle_discovery_message(
                uid, discovered_ip, cast(Optional[int], boot_seqnum)
            )
        )

    async def setup_platforms_and_discovery(self) -> None:
        """Set up platforms and discovery."""
        await self.hass.config_entries.async_forward_entry_setups(self.entry, PLATFORMS)
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
            await self.hass.async_add_executor_job(self._poll_manual_hosts)

        self.entry.async_on_unload(
            await ssdp.async_register_callback(
                self.hass, self._async_ssdp_discovered_player, {"st": UPNP_ST}
            )
        )

        self.entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                partial(
                    async_dispatcher_send,
                    self.hass,
                    SONOS_CHECK_ACTIVITY,
                ),
                AVAILABILITY_CHECK_INTERVAL,
            )
        )


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove Sonos config entry from a device."""
    known_devices = hass.data[DATA_SONOS].discovered.keys()
    for identifier in device_entry.identifiers:
        if identifier[0] != DOMAIN:
            continue
        uid = identifier[1]
        if uid not in known_devices:
            return True
    return False
