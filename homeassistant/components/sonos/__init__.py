"""Support to embed Sonos."""
from __future__ import annotations

import asyncio
import datetime
import logging
import socket

import pysonos
from pysonos import events_asyncio
from pysonos.core import SoCo
from pysonos.exceptions import SoCoException
import voluptuous as vol

from homeassistant import config_entries
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

from .const import (
    DATA_SONOS,
    DISCOVERY_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SONOS_GROUP_UPDATE,
    SONOS_SEEN,
)
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)

CONF_ADVERTISE_ADDR = "advertise_addr"
CONF_INTERFACE_ADDR = "interface_addr"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                MP_DOMAIN: vol.Schema(
                    {
                        vol.Optional(CONF_ADVERTISE_ADDR): cv.string,
                        vol.Optional(CONF_INTERFACE_ADDR): cv.string,
                        vol.Optional(CONF_HOSTS): vol.All(
                            cv.ensure_list_csv, [cv.string]
                        ),
                    }
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class SonosData:
    """Storage class for platform global data."""

    def __init__(self) -> None:
        """Initialize the data."""
        self.discovered: dict[str, SonosSpeaker] = {}
        self.media_player_entities = {}
        self.topology_condition = asyncio.Condition()
        self.discovery_thread = None
        self.hosts_heartbeat = None
        self.platforms_ready: set[str] = set()


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
    pysonos.config.EVENTS_MODULE = events_asyncio

    if DATA_SONOS not in hass.data:
        hass.data[DATA_SONOS] = SonosData()

    config = hass.data[DOMAIN].get("media_player", {})
    _LOGGER.debug("Reached async_setup_entry, config=%s", config)

    advertise_addr = config.get(CONF_ADVERTISE_ADDR)
    if advertise_addr:
        pysonos.config.EVENT_ADVERTISE_IP = advertise_addr

    def _stop_discovery(event: Event) -> None:
        data = hass.data[DATA_SONOS]
        if data.discovery_thread:
            data.discovery_thread.stop()
            data.discovery_thread = None
        if data.hosts_heartbeat:
            data.hosts_heartbeat()
            data.hosts_heartbeat = None

    def _discovery(now: datetime.datetime | None = None) -> None:
        """Discover players from network or configuration."""
        hosts = config.get(CONF_HOSTS)

        def _discovered_player(soco: SoCo) -> None:
            """Handle a (re)discovered player."""
            try:
                _LOGGER.debug("Reached _discovered_player, soco=%s", soco)

                data = hass.data[DATA_SONOS]

                if soco.uid not in data.discovered:
                    _LOGGER.debug("Adding new speaker")
                    speaker_info = soco.get_speaker_info(True)
                    speaker = SonosSpeaker(hass, soco, speaker_info)
                    data.discovered[soco.uid] = speaker
                    speaker.setup()
                else:
                    dispatcher_send(hass, f"{SONOS_SEEN}-{soco.uid}", soco)

            except SoCoException as ex:
                _LOGGER.debug("SoCoException, ex=%s", ex)

        if hosts:
            for host in hosts:
                try:
                    _LOGGER.debug("Testing %s", host)
                    player = pysonos.SoCo(socket.gethostbyname(host))
                    if player.is_visible:
                        # Make sure that the player is available
                        _ = player.volume

                        _discovered_player(player)
                except (OSError, SoCoException) as ex:
                    _LOGGER.debug("Exception %s", ex)
                    if now is None:
                        _LOGGER.warning("Failed to initialize '%s'", host)

            _LOGGER.debug("Tested all hosts")
            hass.data[DATA_SONOS].hosts_heartbeat = hass.helpers.event.call_later(
                DISCOVERY_INTERVAL.total_seconds(), _discovery
            )
        else:
            _LOGGER.debug("Starting discovery thread")
            hass.data[DATA_SONOS].discovery_thread = pysonos.discover_thread(
                _discovered_player,
                interval=DISCOVERY_INTERVAL.total_seconds(),
                interface_addr=config.get(CONF_INTERFACE_ADDR),
            )
            hass.data[DATA_SONOS].discovery_thread.name = "Sonos-Discovery"

    @callback
    def _async_signal_update_groups(event):
        async_dispatcher_send(hass, SONOS_GROUP_UPDATE)

    async def setup_platforms_and_discovery():
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS
            ]
        )
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_discovery)
        )
        entry.async_on_unload(
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, _async_signal_update_groups
            )
        )
        _LOGGER.debug("Adding discovery job")
        await hass.async_add_executor_job(_discovery)

    hass.async_create_task(setup_platforms_and_discovery())

    return True
