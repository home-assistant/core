"""Support for Bluesound devices."""
from __future__ import annotations

import asyncio
from asyncio import CancelledError
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any
from urllib import parse

import aiohttp
from aiohttp.client_exceptions import ClientError
from aiohttp.hdrs import CONNECTION, KEEP_ALIVE
import async_timeout
import voluptuous as vol
import xmltodict

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_HOSTS,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    SERVICE_CLEAR_TIMER,
    SERVICE_JOIN,
    SERVICE_SET_TIMER,
    SERVICE_UNJOIN,
)

_LOGGER = logging.getLogger(__name__)

ATTR_BLUESOUND_GROUP = "bluesound_group"
ATTR_MASTER = "master"

DATA_BLUESOUND = "bluesound"
DEFAULT_PORT = 11000

NODE_OFFLINE_CHECK_TIMEOUT = 180
NODE_RETRY_INITIATION = timedelta(minutes=3)

SYNC_STATUS_INTERVAL = timedelta(minutes=5)

UPDATE_CAPTURE_INTERVAL = timedelta(minutes=30)
UPDATE_PRESETS_INTERVAL = timedelta(minutes=30)
UPDATE_SERVICES_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOSTS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                }
            ],
        )
    }
)

BS_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

BS_JOIN_SCHEMA = BS_SCHEMA.extend({vol.Required(ATTR_MASTER): cv.entity_id})

SERVICE_TO_METHOD = {
    SERVICE_JOIN: {"method": "async_join", "schema": BS_JOIN_SCHEMA},
    SERVICE_UNJOIN: {"method": "async_unjoin", "schema": BS_SCHEMA},
    SERVICE_SET_TIMER: {"method": "async_increase_timer", "schema": BS_SCHEMA},
    SERVICE_CLEAR_TIMER: {"method": "async_clear_timer", "schema": BS_SCHEMA},
}


def _add_player(hass, async_add_entities, host, port=None, name=None):
    """Add Bluesound players."""

    @callback
    def _init_player(event=None):
        """Start polling."""
        hass.async_create_task(player.async_init())

    @callback
    def _start_polling(event=None):
        """Start polling."""
        player.start_polling()

    @callback
    def _stop_polling():
        """Stop polling."""
        player.stop_polling()

    @callback
    def _add_player_cb():
        """Add player after first sync fetch."""
        if player.id in [x.id for x in hass.data[DATA_BLUESOUND]]:
            _LOGGER.warning("Player already added %s", player.id)
            return

        hass.data[DATA_BLUESOUND].append(player)
        async_add_entities([player])
        _LOGGER.info("Added device with name: %s", player.name)

        if hass.is_running:
            _start_polling()
        else:
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _start_polling)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_polling)

    player = BluesoundPlayer(hass, host, port, name, _add_player_cb)

    if hass.is_running:
        _init_player()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _init_player)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Bluesound platforms."""
    if DATA_BLUESOUND not in hass.data:
        hass.data[DATA_BLUESOUND] = []

    if discovery_info:
        _add_player(
            hass,
            async_add_entities,
            discovery_info.get(CONF_HOST),
            discovery_info.get(CONF_PORT),
        )
        return

    if hosts := config.get(CONF_HOSTS):
        for host in hosts:
            _add_player(
                hass,
                async_add_entities,
                host.get(CONF_HOST),
                host.get(CONF_PORT),
                host.get(CONF_NAME),
            )

    async def async_service_handler(service: ServiceCall) -> None:
        """Map services to method of Bluesound devices."""
        if not (method := SERVICE_TO_METHOD.get(service.service)):
            return

        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        if entity_ids := service.data.get(ATTR_ENTITY_ID):
            target_players = [
                player
                for player in hass.data[DATA_BLUESOUND]
                if player.entity_id in entity_ids
            ]
        else:
            target_players = hass.data[DATA_BLUESOUND]

        for player in target_players:
            await getattr(player, method["method"])(**params)

    for service, method in SERVICE_TO_METHOD.items():
        schema = method["schema"]
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=schema
        )


class BluesoundPlayer(MediaPlayerEntity):
    """Representation of a Bluesound Player."""

    _attr_media_content_type = MediaType.MUSIC

    def __init__(self, hass, host, port=None, name=None, init_callback=None):
        """Initialize the media player."""
        self.host = host
        self._hass = hass
        self.port = port
        self._polling_session = async_get_clientsession(hass)
        self._polling_task = None  # The actual polling task.
        self._name = name
        self._id = None
        self._capture_items = []
        self._services_items = []
        self._preset_items = []
        self._sync_status = {}
        self._status = None
        self._last_status_update = None
        self._is_online = False
        self._retry_remove = None
        self._muted = False
        self._master = None
        self._is_master = False
        self._group_name = None
        self._group_list = []
        self._bluesound_device_name = None

        self._init_callback = init_callback

        if self.port is None:
            self.port = DEFAULT_PORT

    class _TimeoutException(Exception):
        pass

    @staticmethod
    def _try_get_index(string, search_string):
        """Get the index."""
        try:
            return string.index(search_string)
        except ValueError:
            return -1

    async def force_update_sync_status(self, on_updated_cb=None, raise_timeout=False):
        """Update the internal status."""
        resp = await self.send_bluesound_command(
            "SyncStatus", raise_timeout, raise_timeout
        )

        if not resp:
            return None
        self._sync_status = resp["SyncStatus"].copy()

        if not self._name:
            self._name = self._sync_status.get("@name", self.host)
        if not self._id:
            self._id = self._sync_status.get("@id", None)
        if not self._bluesound_device_name:
            self._bluesound_device_name = self._sync_status.get("@name", self.host)

        if (master := self._sync_status.get("master")) is not None:
            self._is_master = False
            master_host = master.get("#text")
            master_port = master.get("@port", "11000")
            master_id = f"{master_host}:{master_port}"
            master_device = [
                device
                for device in self._hass.data[DATA_BLUESOUND]
                if device.id == master_id
            ]

            if master_device and master_id != self.id:
                self._master = master_device[0]
            else:
                self._master = None
                _LOGGER.error("Master not found %s", master_id)
        else:
            if self._master is not None:
                self._master = None
            slaves = self._sync_status.get("slave")
            self._is_master = slaves is not None

        if on_updated_cb:
            on_updated_cb()
        return True

    async def _start_poll_command(self):
        """Loop which polls the status of the player."""
        try:
            while True:
                await self.async_update_status()

        except (asyncio.TimeoutError, ClientError, BluesoundPlayer._TimeoutException):
            _LOGGER.info("Node %s:%s is offline, retrying later", self.name, self.port)
            await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT)
            self.start_polling()

        except CancelledError:
            _LOGGER.debug("Stopping the polling of node %s:%s", self.name, self.port)
        except Exception:
            _LOGGER.exception("Unexpected error in %s:%s", self.name, self.port)
            raise

    def start_polling(self):
        """Start the polling task."""
        self._polling_task = self._hass.async_create_task(self._start_poll_command())

    def stop_polling(self):
        """Stop the polling task."""
        self._polling_task.cancel()

    async def async_init(self, triggered=None):
        """Initialize the player async."""
        try:
            if self._retry_remove is not None:
                self._retry_remove()
                self._retry_remove = None

            await self.force_update_sync_status(self._init_callback, True)
        except (asyncio.TimeoutError, ClientError):
            _LOGGER.info("Node %s:%s is offline, retrying later", self.host, self.port)
            self._retry_remove = async_track_time_interval(
                self._hass, self.async_init, NODE_RETRY_INITIATION
            )
        except Exception:
            _LOGGER.exception(
                "Unexpected when initiating error in %s:%s", self.host, self.port
            )
            raise

    async def async_update(self) -> None:
        """Update internal status of the entity."""
        if not self._is_online:
            return

        await self.async_update_sync_status()
        await self.async_update_presets()
        await self.async_update_captures()
        await self.async_update_services()

    async def send_bluesound_command(
        self, method, raise_timeout=False, allow_offline=False
    ):
        """Send command to the player."""
        if not self._is_online and not allow_offline:
            return

        if method[0] == "/":
            method = method[1:]
        url = f"http://{self.host}:{self.port}/{method}"

        _LOGGER.debug("Calling URL: %s", url)
        response = None

        try:
            websession = async_get_clientsession(self._hass)
            async with async_timeout.timeout(10):
                response = await websession.get(url)

            if response.status == HTTPStatus.OK:
                result = await response.text()
                if result:
                    data = xmltodict.parse(result)
                else:
                    data = None
            elif response.status == 595:
                _LOGGER.info("Status 595 returned, treating as timeout")
                raise BluesoundPlayer._TimeoutException()
            else:
                _LOGGER.error("Error %s on %s", response.status, url)
                return None

        except (asyncio.TimeoutError, aiohttp.ClientError):
            if raise_timeout:
                _LOGGER.info("Timeout: %s:%s", self.host, self.port)
                raise
            _LOGGER.debug("Failed communicating: %s:%s", self.host, self.port)
            return None

        return data

    async def async_update_status(self):
        """Use the poll session to always get the status of the player."""
        response = None

        url = "Status"
        etag = ""
        if self._status is not None:
            etag = self._status.get("@etag", "")

        if etag != "":
            url = f"Status?etag={etag}&timeout=120.0"
        url = f"http://{self.host}:{self.port}/{url}"

        _LOGGER.debug("Calling URL: %s", url)

        try:
            async with async_timeout.timeout(125):
                response = await self._polling_session.get(
                    url, headers={CONNECTION: KEEP_ALIVE}
                )

            if response.status == HTTPStatus.OK:
                result = await response.text()
                self._is_online = True
                self._last_status_update = dt_util.utcnow()
                self._status = xmltodict.parse(result)["status"].copy()

                group_name = self._status.get("groupName")
                if group_name != self._group_name:
                    _LOGGER.debug("Group name change detected on device: %s", self.id)
                    self._group_name = group_name

                    # rebuild ordered list of entity_ids that are in the group, master is first
                    self._group_list = self.rebuild_bluesound_group()

                    # the sleep is needed to make sure that the
                    # devices is synced
                    await asyncio.sleep(1)
                    await self.async_trigger_sync_on_all()
                elif self.is_grouped:
                    # when player is grouped we need to fetch volume from
                    # sync_status. We will force an update if the player is
                    # grouped this isn't a foolproof solution. A better
                    # solution would be to fetch sync_status more often when
                    # the device is playing. This would solve a lot of
                    # problems. This change will be done when the
                    # communication is moved to a separate library
                    await self.force_update_sync_status()

                self.async_write_ha_state()
            elif response.status == 595:
                _LOGGER.info("Status 595 returned, treating as timeout")
                raise BluesoundPlayer._TimeoutException()
            else:
                _LOGGER.error(
                    "Error %s on %s. Trying one more time", response.status, url
                )

        except (asyncio.TimeoutError, ClientError):
            self._is_online = False
            self._last_status_update = None
            self._status = None
            self.async_write_ha_state()
            _LOGGER.info("Client connection error, marking %s as offline", self._name)
            raise

    @property
    def unique_id(self):
        """Return an unique ID."""
        return f"{format_mac(self._sync_status['@mac'])}-{self.port}"

    async def async_trigger_sync_on_all(self):
        """Trigger sync status update on all devices."""
        _LOGGER.debug("Trigger sync status on all devices")

        for player in self._hass.data[DATA_BLUESOUND]:
            await player.force_update_sync_status()

    @Throttle(SYNC_STATUS_INTERVAL)
    async def async_update_sync_status(self, on_updated_cb=None, raise_timeout=False):
        """Update sync status."""
        await self.force_update_sync_status(on_updated_cb, raise_timeout=False)

    @Throttle(UPDATE_CAPTURE_INTERVAL)
    async def async_update_captures(self):
        """Update Capture sources."""
        resp = await self.send_bluesound_command("RadioBrowse?service=Capture")
        if not resp:
            return
        self._capture_items = []

        def _create_capture_item(item):
            self._capture_items.append(
                {
                    "title": item.get("@text", ""),
                    "name": item.get("@text", ""),
                    "type": item.get("@serviceType", "Capture"),
                    "image": item.get("@image", ""),
                    "url": item.get("@URL", ""),
                }
            )

        if "radiotime" in resp and "item" in resp["radiotime"]:
            if isinstance(resp["radiotime"]["item"], list):
                for item in resp["radiotime"]["item"]:
                    _create_capture_item(item)
            else:
                _create_capture_item(resp["radiotime"]["item"])

        return self._capture_items

    @Throttle(UPDATE_PRESETS_INTERVAL)
    async def async_update_presets(self):
        """Update Presets."""
        resp = await self.send_bluesound_command("Presets")
        if not resp:
            return
        self._preset_items = []

        def _create_preset_item(item):
            self._preset_items.append(
                {
                    "title": item.get("@name", ""),
                    "name": item.get("@name", ""),
                    "type": "preset",
                    "image": item.get("@image", ""),
                    "is_raw_url": True,
                    "url2": item.get("@url", ""),
                    "url": f"Preset?id={item.get('@id', '')}",
                }
            )

        if "presets" in resp and "preset" in resp["presets"]:
            if isinstance(resp["presets"]["preset"], list):
                for item in resp["presets"]["preset"]:
                    _create_preset_item(item)
            else:
                _create_preset_item(resp["presets"]["preset"])

        return self._preset_items

    @Throttle(UPDATE_SERVICES_INTERVAL)
    async def async_update_services(self):
        """Update Services."""
        resp = await self.send_bluesound_command("Services")
        if not resp:
            return
        self._services_items = []

        def _create_service_item(item):
            self._services_items.append(
                {
                    "title": item.get("@displayname", ""),
                    "name": item.get("@name", ""),
                    "type": item.get("@type", ""),
                    "image": item.get("@icon", ""),
                    "url": item.get("@name", ""),
                }
            )

        if "services" in resp and "service" in resp["services"]:
            if isinstance(resp["services"]["service"], list):
                for item in resp["services"]["service"]:
                    _create_service_item(item)
            else:
                _create_service_item(resp["services"]["service"])

        return self._services_items

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        if self._status is None:
            return MediaPlayerState.OFF

        if self.is_grouped and not self.is_master:
            return MediaPlayerState.IDLE

        status = self._status.get("state")
        if status in ("pause", "stop"):
            return MediaPlayerState.PAUSED
        if status in ("stream", "play"):
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        return self._status.get("title1")

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        if self._status is None:
            return None

        if self.is_grouped and not self.is_master:
            return self._group_name

        if not (artist := self._status.get("artist")):
            artist = self._status.get("title2")
        return artist

    @property
    def media_album_name(self):
        """Artist of current playing media (Music track only)."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        if not (album := self._status.get("album")):
            album = self._status.get("title3")
        return album

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        if not (url := self._status.get("image")):
            return
        if url[0] == "/":
            url = f"http://{self.host}:{self.port}{url}"

        return url

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        mediastate = self.state
        if self._last_status_update is None or mediastate == MediaPlayerState.IDLE:
            return None

        if (position := self._status.get("secs")) is None:
            return None

        position = float(position)
        if mediastate == MediaPlayerState.PLAYING:
            position += (dt_util.utcnow() - self._last_status_update).total_seconds()

        return position

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        if (duration := self._status.get("totlen")) is None:
            return None
        return float(duration)

    @property
    def media_position_updated_at(self):
        """Last time status was updated."""
        return self._last_status_update

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume = self._status.get("volume")
        if self.is_grouped:
            volume = self._sync_status.get("@volume")

        if volume is not None:
            return int(volume) / 100
        return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        mute = self._status.get("mute")
        if self.is_grouped:
            mute = self._sync_status.get("@mute")

        if mute is not None:
            mute = bool(int(mute))
        return mute

    @property
    def id(self):
        """Get id of device."""
        return self._id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def bluesound_device_name(self):
        """Return the device name as returned by the device."""
        return self._bluesound_device_name

    @property
    def source_list(self):
        """List of available input sources."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        sources = []

        for source in self._preset_items:
            sources.append(source["title"])

        for source in [
            x
            for x in self._services_items
            if x["type"] in ("LocalMusic", "RadioService")
        ]:
            sources.append(source["title"])

        for source in self._capture_items:
            sources.append(source["title"])

        return sources

    @property
    def source(self):
        """Name of the current input source."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        if (current_service := self._status.get("service", "")) == "":
            return ""
        stream_url = self._status.get("streamUrl", "")

        if self._status.get("is_preset", "") == "1" and stream_url != "":
            # This check doesn't work with all presets, for example playlists.
            # But it works with radio service_items will catch playlists.
            items = [
                x
                for x in self._preset_items
                if "url2" in x and parse.unquote(x["url2"]) == stream_url
            ]
            if items:
                return items[0]["title"]

        # This could be a bit difficult to detect. Bluetooth could be named
        # different things and there is not any way to match chooses in
        # capture list to current playing. It's a bit of guesswork.
        # This method will be needing some tweaking over time.
        title = self._status.get("title1", "").lower()
        if title == "bluetooth" or stream_url == "Capture:hw:2,0/44100/16/2":
            items = [
                x
                for x in self._capture_items
                if x["url"] == "Capture%3Abluez%3Abluetooth"
            ]
            if items:
                return items[0]["title"]

        items = [x for x in self._capture_items if x["url"] == stream_url]
        if items:
            return items[0]["title"]

        if stream_url[:8] == "Capture:":
            stream_url = stream_url[8:]

        idx = BluesoundPlayer._try_get_index(stream_url, ":")
        if idx > 0:
            stream_url = stream_url[:idx]
            for item in self._capture_items:
                url = parse.unquote(item["url"])
                if url[:8] == "Capture:":
                    url = url[8:]
                idx = BluesoundPlayer._try_get_index(url, ":")
                if idx > 0:
                    url = url[:idx]
                if url.lower() == stream_url.lower():
                    return item["title"]

        items = [x for x in self._capture_items if x["name"] == current_service]
        if items:
            return items[0]["title"]

        items = [x for x in self._services_items if x["name"] == current_service]
        if items:
            return items[0]["title"]

        if self._status.get("streamUrl", "") != "":
            _LOGGER.debug(
                "Couldn't find source of stream URL: %s",
                self._status.get("streamUrl", ""),
            )
        return None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag of media commands that are supported."""
        if self._status is None:
            return MediaPlayerEntityFeature(0)

        if self.is_grouped and not self.is_master:
            return (
                MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
            )

        supported = (
            MediaPlayerEntityFeature.CLEAR_PLAYLIST
            | MediaPlayerEntityFeature.BROWSE_MEDIA
        )

        if self._status.get("indexing", "0") == "0":
            supported = (
                supported
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
                | MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.SELECT_SOURCE
                | MediaPlayerEntityFeature.SHUFFLE_SET
            )

        current_vol = self.volume_level
        if current_vol is not None and current_vol >= 0:
            supported = (
                supported
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
            )

        if self._status.get("canSeek", "") == "1":
            supported = supported | MediaPlayerEntityFeature.SEEK

        return supported

    @property
    def is_master(self):
        """Return true if player is a coordinator."""
        return self._is_master

    @property
    def is_grouped(self):
        """Return true if player is a coordinator."""
        return self._master is not None or self._is_master

    @property
    def shuffle(self):
        """Return true if shuffle is active."""
        return self._status.get("shuffle", "0") == "1"

    async def async_join(self, master):
        """Join the player to a group."""
        master_device = [
            device
            for device in self.hass.data[DATA_BLUESOUND]
            if device.entity_id == master
        ]

        if master_device:
            _LOGGER.debug(
                "Trying to join player: %s to master: %s",
                self.id,
                master_device[0].id,
            )

            await master_device[0].async_add_slave(self)
        else:
            _LOGGER.error("Master not found %s", master_device)

    @property
    def extra_state_attributes(self):
        """List members in group."""
        attributes = {}
        if self._group_list:
            attributes = {ATTR_BLUESOUND_GROUP: self._group_list}

        attributes[ATTR_MASTER] = self._is_master

        return attributes

    def rebuild_bluesound_group(self):
        """Rebuild the list of entities in speaker group."""
        if self._group_name is None:
            return None

        bluesound_group = []

        device_group = self._group_name.split("+")

        sorted_entities = sorted(
            self._hass.data[DATA_BLUESOUND],
            key=lambda entity: entity.is_master,
            reverse=True,
        )
        bluesound_group = [
            entity.name
            for entity in sorted_entities
            if entity.bluesound_device_name in device_group
        ]

        return bluesound_group

    async def async_unjoin(self):
        """Unjoin the player from a group."""
        if self._master is None:
            return

        _LOGGER.debug("Trying to unjoin player: %s", self.id)
        await self._master.async_remove_slave(self)

    async def async_add_slave(self, slave_device):
        """Add slave to master."""
        return await self.send_bluesound_command(
            f"/AddSlave?slave={slave_device.host}&port={slave_device.port}"
        )

    async def async_remove_slave(self, slave_device):
        """Remove slave to master."""
        return await self.send_bluesound_command(
            f"/RemoveSlave?slave={slave_device.host}&port={slave_device.port}"
        )

    async def async_increase_timer(self):
        """Increase sleep time on player."""
        sleep_time = await self.send_bluesound_command("/Sleep")
        if sleep_time is None:
            _LOGGER.error("Error while increasing sleep time on player: %s", self.id)
            return 0

        return int(sleep_time.get("sleep", "0"))

    async def async_clear_timer(self):
        """Clear sleep timer on player."""
        sleep = 1
        while sleep > 0:
            sleep = await self.async_increase_timer()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable or disable shuffle mode."""
        value = "1" if shuffle else "0"
        return await self.send_bluesound_command(f"/Shuffle?state={value}")

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if self.is_grouped and not self.is_master:
            return

        items = [x for x in self._preset_items if x["title"] == source]

        if not items:
            items = [x for x in self._services_items if x["title"] == source]
        if not items:
            items = [x for x in self._capture_items if x["title"] == source]

        if not items:
            return

        selected_source = items[0]
        url = f"Play?url={selected_source['url']}&preset_id&image={selected_source['image']}"

        if "is_raw_url" in selected_source and selected_source["is_raw_url"]:
            url = selected_source["url"]

        return await self.send_bluesound_command(url)

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        if self.is_grouped and not self.is_master:
            return

        return await self.send_bluesound_command("Clear")

    async def async_media_next_track(self) -> None:
        """Send media_next command to media player."""
        if self.is_grouped and not self.is_master:
            return

        cmd = "Skip"
        if self._status and "actions" in self._status:
            for action in self._status["actions"]["action"]:
                if "@name" in action and "@url" in action and action["@name"] == "skip":
                    cmd = action["@url"]

        return await self.send_bluesound_command(cmd)

    async def async_media_previous_track(self) -> None:
        """Send media_previous command to media player."""
        if self.is_grouped and not self.is_master:
            return

        cmd = "Back"
        if self._status and "actions" in self._status:
            for action in self._status["actions"]["action"]:
                if "@name" in action and "@url" in action and action["@name"] == "back":
                    cmd = action["@url"]

        return await self.send_bluesound_command(cmd)

    async def async_media_play(self) -> None:
        """Send media_play command to media player."""
        if self.is_grouped and not self.is_master:
            return

        return await self.send_bluesound_command("Play")

    async def async_media_pause(self) -> None:
        """Send media_pause command to media player."""
        if self.is_grouped and not self.is_master:
            return

        return await self.send_bluesound_command("Pause")

    async def async_media_stop(self) -> None:
        """Send stop command."""
        if self.is_grouped and not self.is_master:
            return

        return await self.send_bluesound_command("Pause")

    async def async_media_seek(self, position: float) -> None:
        """Send media_seek command to media player."""
        if self.is_grouped and not self.is_master:
            return

        return await self.send_bluesound_command(f"Play?seek={float(position)}")

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play_media command to the media player."""
        if self.is_grouped and not self.is_master:
            return

        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        media_id = async_process_play_media_url(self.hass, media_id)

        url = f"Play?url={media_id}"

        return await self.send_bluesound_command(url)

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        current_vol = self.volume_level
        if not current_vol or current_vol >= 1:
            return
        return await self.async_set_volume_level(current_vol + 0.01)

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        current_vol = self.volume_level
        if not current_vol or current_vol <= 0:
            return
        return await self.async_set_volume_level(current_vol - 0.01)

    async def async_set_volume_level(self, volume: float) -> None:
        """Send volume_up command to media player."""
        if volume < 0:
            volume = 0
        elif volume > 1:
            volume = 1
        return await self.send_bluesound_command(f"Volume?level={float(volume) * 100}")

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command to media player."""
        if mute:
            return await self.send_bluesound_command("Volume?mute=1")
        return await self.send_bluesound_command("Volume?mute=0")

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )
