"""Support to embed Sonos."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import datetime
from enum import Enum
import logging
import socket
from urllib.parse import urlparse

import pysonos
from pysonos import events_asyncio
from pysonos.core import SoCo
from pysonos.exceptions import SoCoException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOSTS,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send

from .alarms import SonosAlarms
from .const import (
    DATA_SONOS,
    DISCOVERY_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SONOS_GROUP_UPDATE,
    SONOS_REBOOTED,
    SONOS_SEEN,
    UPNP_ST,
)
from .favorites import SonosFavorites
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)

CONF_ADVERTISE_ADDR = "advertise_addr"
CONF_INTERFACE_ADDR = "interface_addr"


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
        self.ssdp_known: set[str] = set()
        self.boot_counts: dict[str, int] = {}


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


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Sonos from a config entry."""
    pysonos.config.EVENTS_MODULE = events_asyncio

    if DATA_SONOS not in hass.data:
        hass.data[DATA_SONOS] = SonosData()

    data = hass.data[DATA_SONOS]
    config = hass.data[DOMAIN].get("media_player", {})
    hosts = config.get(CONF_HOSTS, [])
    discovery_lock = asyncio.Lock()
    _LOGGER.debug("Reached async_setup_entry, config=%s", config)

    advertise_addr = config.get(CONF_ADVERTISE_ADDR)
    if advertise_addr:
        pysonos.config.EVENT_ADVERTISE_IP = advertise_addr

    if deprecated_address := config.get(CONF_INTERFACE_ADDR):
        _LOGGER.warning(
            "'%s' is deprecated, enable %s in the Network integration (https://www.home-assistant.io/integrations/network/)",
            CONF_INTERFACE_ADDR,
            deprecated_address,
        )

    async def _async_stop_event_listener(event: Event) -> None:
        await asyncio.gather(
            *[speaker.async_unsubscribe() for speaker in data.discovered.values()],
            return_exceptions=True,
        )
        if events_asyncio.event_listener:
            await events_asyncio.event_listener.async_stop()

    def _stop_manual_heartbeat(event: Event) -> None:
        if data.hosts_heartbeat:
            data.hosts_heartbeat()
            data.hosts_heartbeat = None

    def _discovered_player(soco: SoCo) -> None:
        """Handle a (re)discovered player."""
        try:
            speaker_info = soco.get_speaker_info(True)
            _LOGGER.debug("Adding new speaker: %s", speaker_info)
            speaker = SonosSpeaker(hass, soco, speaker_info)
            data.discovered[soco.uid] = speaker
            for coordinator, coord_dict in [
                (SonosAlarms, data.alarms),
                (SonosFavorites, data.favorites),
            ]:
                if soco.household_id not in coord_dict:
                    new_coordinator = coordinator(hass, soco.household_id)
                    new_coordinator.setup(soco)
                    coord_dict[soco.household_id] = new_coordinator
            speaker.setup()
        except (OSError, SoCoException):
            _LOGGER.warning("Failed to add SonosSpeaker using %s", soco, exc_info=True)

    def _create_soco(ip_address: str, source: SoCoCreationSource) -> SoCo | None:
        """Create a soco instance and return if successful."""
        try:
            soco = pysonos.SoCo(ip_address)
            # Ensure that the player is available and UID is cached
            _ = soco.uid
            _ = soco.volume
            return soco
        except (OSError, SoCoException) as ex:
            _LOGGER.warning(
                "Failed to connect to %s player '%s': %s", source.value, ip_address, ex
            )
        return None

    def _manual_hosts(now: datetime.datetime | None = None) -> None:
        """Players from network configuration."""
        for host in hosts:
            ip_addr = socket.gethostbyname(host)
            known_uid = next(
                (
                    uid
                    for uid, speaker in data.discovered.items()
                    if speaker.soco.ip_address == ip_addr
                ),
                None,
            )

            if known_uid:
                dispatcher_send(hass, f"{SONOS_SEEN}-{known_uid}")
            else:
                soco = _create_soco(ip_addr, SoCoCreationSource.CONFIGURED)
                if soco and soco.is_visible:
                    _discovered_player(soco)

        data.hosts_heartbeat = hass.helpers.event.call_later(
            DISCOVERY_INTERVAL.total_seconds(), _manual_hosts
        )

    @callback
    def _async_signal_update_groups(event):
        async_dispatcher_send(hass, SONOS_GROUP_UPDATE)

    def _discovered_ip(ip_address):
        soco = _create_soco(ip_address, SoCoCreationSource.DISCOVERED)
        if soco and soco.is_visible:
            _discovered_player(soco)

    async def _async_create_discovered_player(uid, discovered_ip, boot_seqnum):
        """Only create one player at a time."""
        async with discovery_lock:
            if uid not in data.discovered:
                await hass.async_add_executor_job(_discovered_ip, discovered_ip)
                return

            if boot_seqnum and boot_seqnum > data.boot_counts[uid]:
                data.boot_counts[uid] = boot_seqnum
                if soco := await hass.async_add_executor_job(
                    _create_soco, discovered_ip, SoCoCreationSource.REBOOTED
                ):
                    async_dispatcher_send(hass, f"{SONOS_REBOOTED}-{uid}", soco)
            else:
                async_dispatcher_send(hass, f"{SONOS_SEEN}-{uid}")

    @callback
    def _async_discovered_player(info):
        uid = info.get(ssdp.ATTR_UPNP_UDN)
        if uid.startswith("uuid:"):
            uid = uid[5:]
        if boot_seqnum := info.get("X-RINCON-BOOTSEQ"):
            boot_seqnum = int(boot_seqnum)
            data.boot_counts.setdefault(uid, boot_seqnum)
        if uid not in data.ssdp_known:
            _LOGGER.debug("New discovery: %s", info)
            data.ssdp_known.add(uid)
        discovered_ip = urlparse(info[ssdp.ATTR_SSDP_LOCATION]).hostname
        asyncio.create_task(
            _async_create_discovered_player(uid, discovered_ip, boot_seqnum)
        )

    async def setup_platforms_and_discovery():
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS
            ]
        )
        entry.async_on_unload(
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, _async_signal_update_groups
            )
        )
        entry.async_on_unload(
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, _async_stop_event_listener
            )
        )
        _LOGGER.debug("Adding discovery job")
        if hosts:
            entry.async_on_unload(
                hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, _stop_manual_heartbeat
                )
            )
            await hass.async_add_executor_job(_manual_hosts)
            return

        entry.async_on_unload(
            ssdp.async_register_callback(
                hass, _async_discovered_player, {"st": UPNP_ST}
            )
        )

    hass.async_create_task(setup_platforms_and_discovery())

    return True
