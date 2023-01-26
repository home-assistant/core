"""Support for DLNA DMR (Device Media Renderer)."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Sequence
import contextlib
from datetime import datetime, timedelta
import functools
from typing import Any, Concatenate, ParamSpec, TypeVar

from async_upnp_client.client import UpnpService, UpnpStateVariable
from async_upnp_client.const import NotificationSubType
from async_upnp_client.exceptions import UpnpError, UpnpResponseError
from async_upnp_client.profiles.dlna import DmrDevice, PlayMode, TransportState
from async_upnp_client.utils import async_get_local_ip
from didl_lite import didl_lite

from homeassistant import config_entries
from homeassistant.components import media_source, ssdp
from homeassistant.components.media_player import (
    ATTR_MEDIA_EXTRA,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_MAC, CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BROWSE_UNFILTERED,
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DOMAIN,
    LOGGER as _LOGGER,
    MEDIA_METADATA_DIDL,
    MEDIA_TYPE_MAP,
    MEDIA_UPNP_CLASS_MAP,
    REPEAT_PLAY_MODES,
    SHUFFLE_PLAY_MODES,
    STREAMABLE_PROTOCOLS,
)
from .data import EventListenAddr, get_domain_data

PARALLEL_UPDATES = 0

_DlnaDmrEntityT = TypeVar("_DlnaDmrEntityT", bound="DlnaDmrEntity")
_R = TypeVar("_R")
_P = ParamSpec("_P")


def catch_request_errors(
    func: Callable[Concatenate[_DlnaDmrEntityT, _P], Awaitable[_R]]
) -> Callable[Concatenate[_DlnaDmrEntityT, _P], Coroutine[Any, Any, _R | None]]:
    """Catch UpnpError errors."""

    @functools.wraps(func)
    async def wrapper(
        self: _DlnaDmrEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R | None:
        """Catch UpnpError errors and check availability before and after request."""
        if not self.available:
            _LOGGER.warning(
                "Device disappeared when trying to call service %s", func.__name__
            )
            return None
        try:
            return await func(self, *args, **kwargs)
        except UpnpError as err:
            self.check_available = True
            _LOGGER.error("Error during call %s: %r", func.__name__, err)
        return None

    return wrapper


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DlnaDmrEntity from a config entry."""
    _LOGGER.debug("media_player.async_setup_entry %s (%s)", entry.entry_id, entry.title)

    # Create our own device-wrapping entity
    entity = DlnaDmrEntity(
        udn=entry.data[CONF_DEVICE_ID],
        device_type=entry.data[CONF_TYPE],
        name=entry.title,
        event_port=entry.options.get(CONF_LISTEN_PORT) or 0,
        event_callback_url=entry.options.get(CONF_CALLBACK_URL_OVERRIDE),
        poll_availability=entry.options.get(CONF_POLL_AVAILABILITY, False),
        location=entry.data[CONF_URL],
        mac_address=entry.data.get(CONF_MAC),
        browse_unfiltered=entry.options.get(CONF_BROWSE_UNFILTERED, False),
    )

    async_add_entities([entity])


class DlnaDmrEntity(MediaPlayerEntity):
    """Representation of a DLNA DMR device as a HA entity."""

    udn: str
    device_type: str

    _event_addr: EventListenAddr
    poll_availability: bool
    # Last known URL for the device, used when adding this entity to hass to try
    # to connect before SSDP has rediscovered it, or when SSDP discovery fails.
    location: str
    # Should the async_browse_media function *not* filter out incompatible media?
    browse_unfiltered: bool

    _device_lock: asyncio.Lock  # Held when connecting or disconnecting the device
    _device: DmrDevice | None = None
    check_available: bool = False
    _ssdp_connect_failed: bool = False

    # Track BOOTID in SSDP advertisements for device changes
    _bootid: int | None = None

    # DMR devices need polling for track position information. async_update will
    # determine whether further device polling is required.
    _attr_should_poll = True

    def __init__(
        self,
        udn: str,
        device_type: str,
        name: str,
        event_port: int,
        event_callback_url: str | None,
        poll_availability: bool,
        location: str,
        mac_address: str | None,
        browse_unfiltered: bool,
    ) -> None:
        """Initialize DLNA DMR entity."""
        self.udn = udn
        self.device_type = device_type
        self._attr_name = name
        self._event_addr = EventListenAddr(None, event_port, event_callback_url)
        self.poll_availability = poll_availability
        self.location = location
        self.mac_address = mac_address
        self.browse_unfiltered = browse_unfiltered
        self._device_lock = asyncio.Lock()

    async def async_added_to_hass(self) -> None:
        """Handle addition."""
        # Update this entity when the associated config entry is modified
        if self.registry_entry and self.registry_entry.config_entry_id:
            config_entry = self.hass.config_entries.async_get_entry(
                self.registry_entry.config_entry_id
            )
            assert config_entry is not None
            self.async_on_remove(
                config_entry.add_update_listener(self.async_config_update_listener)
            )

        # Try to connect to the last known location, but don't worry if not available
        if not self._device:
            try:
                await self._device_connect(self.location)
            except UpnpError as err:
                _LOGGER.debug("Couldn't connect immediately: %r", err)

        # Get SSDP notifications for only this device
        self.async_on_remove(
            await ssdp.async_register_callback(
                self.hass, self.async_ssdp_callback, {"USN": self.usn}
            )
        )

        # async_upnp_client.SsdpListener only reports byebye once for each *UDN*
        # (device name) which often is not the USN (service within the device)
        # that we're interested in. So also listen for byebye advertisements for
        # the UDN, which is reported in the _udn field of the combined_headers.
        self.async_on_remove(
            await ssdp.async_register_callback(
                self.hass,
                self.async_ssdp_callback,
                {"_udn": self.udn, "NTS": NotificationSubType.SSDP_BYEBYE},
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal."""
        await self._device_disconnect()

    async def async_ssdp_callback(
        self, info: ssdp.SsdpServiceInfo, change: ssdp.SsdpChange
    ) -> None:
        """Handle notification from SSDP of device state change."""
        _LOGGER.debug(
            "SSDP %s notification of device %s at %s",
            change,
            info.ssdp_usn,
            info.ssdp_location,
        )

        try:
            bootid_str = info.ssdp_headers[ssdp.ATTR_SSDP_BOOTID]
            bootid: int | None = int(bootid_str, 10)
        except (KeyError, ValueError):
            bootid = None

        if change == ssdp.SsdpChange.UPDATE:
            # This is an announcement that bootid is about to change
            if self._bootid is not None and self._bootid == bootid:
                # Store the new value (because our old value matches) so that we
                # can ignore subsequent ssdp:alive messages
                with contextlib.suppress(KeyError, ValueError):
                    next_bootid_str = info.ssdp_headers[ssdp.ATTR_SSDP_NEXTBOOTID]
                    self._bootid = int(next_bootid_str, 10)
            # Nothing left to do until ssdp:alive comes through
            return

        if self._bootid is not None and self._bootid != bootid:
            # Device has rebooted
            # Maybe connection will succeed now
            self._ssdp_connect_failed = False
            if self._device:
                # Drop existing connection and maybe reconnect
                await self._device_disconnect()
        self._bootid = bootid

        if change == ssdp.SsdpChange.BYEBYE:
            # Device is going away
            if self._device:
                # Disconnect from gone device
                await self._device_disconnect()
            # Maybe the next alive message will result in a successful connection
            self._ssdp_connect_failed = False

        if (
            change == ssdp.SsdpChange.ALIVE
            and not self._device
            and not self._ssdp_connect_failed
        ):
            assert info.ssdp_location
            location = info.ssdp_location
            try:
                await self._device_connect(location)
            except UpnpError as err:
                self._ssdp_connect_failed = True
                _LOGGER.warning(
                    "Failed connecting to recently alive device at %s: %r",
                    location,
                    err,
                )

        # Device could have been de/re-connected, state probably changed
        self.async_write_ha_state()

    async def async_config_update_listener(
        self, hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> None:
        """Handle options update by modifying self in-place."""
        _LOGGER.debug(
            "Updating: %s with data=%s and options=%s",
            self.name,
            entry.data,
            entry.options,
        )
        self.location = entry.data[CONF_URL]
        self.poll_availability = entry.options.get(CONF_POLL_AVAILABILITY, False)
        self.browse_unfiltered = entry.options.get(CONF_BROWSE_UNFILTERED, False)

        new_mac_address = entry.data.get(CONF_MAC)
        if new_mac_address != self.mac_address:
            self.mac_address = new_mac_address
            self._update_device_registry(set_mac=True)

        new_port = entry.options.get(CONF_LISTEN_PORT) or 0
        new_callback_url = entry.options.get(CONF_CALLBACK_URL_OVERRIDE)

        if (
            new_port == self._event_addr.port
            and new_callback_url == self._event_addr.callback_url
        ):
            return

        # Changes to eventing requires a device reconnect for it to update correctly
        await self._device_disconnect()
        # Update _event_addr after disconnecting, to stop the right event listener
        self._event_addr = self._event_addr._replace(
            port=new_port, callback_url=new_callback_url
        )
        try:
            await self._device_connect(self.location)
        except UpnpError as err:
            _LOGGER.warning("Couldn't (re)connect after config change: %r", err)

        # Device was de/re-connected, state might have changed
        self.async_write_ha_state()

    async def _device_connect(self, location: str) -> None:
        """Connect to the device now that it's available."""
        _LOGGER.debug("Connecting to device at %s", location)

        async with self._device_lock:
            if self._device:
                _LOGGER.debug("Trying to connect when device already connected")
                return

            domain_data = get_domain_data(self.hass)

            # Connect to the base UPNP device
            upnp_device = await domain_data.upnp_factory.async_create_device(location)

            # Create/get event handler that is reachable by the device, using
            # the connection's local IP to listen only on the relevant interface
            _, event_ip = await async_get_local_ip(location, self.hass.loop)
            self._event_addr = self._event_addr._replace(host=event_ip)
            event_handler = await domain_data.async_get_event_notifier(
                self._event_addr, self.hass
            )

            # Create profile wrapper
            self._device = DmrDevice(upnp_device, event_handler)

            self.location = location

            # Subscribe to event notifications
            try:
                self._device.on_event = self._on_event
                await self._device.async_subscribe_services(auto_resubscribe=True)
            except UpnpResponseError as err:
                # Device rejected subscription request. This is OK, variables
                # will be polled instead.
                _LOGGER.debug("Device rejected subscription: %r", err)
            except UpnpError as err:
                # Don't leave the device half-constructed
                self._device.on_event = None
                self._device = None
                await domain_data.async_release_event_notifier(self._event_addr)
                _LOGGER.debug("Error while subscribing during device connect: %r", err)
                raise

        self._update_device_registry()

    def _update_device_registry(self, set_mac: bool = False) -> None:
        """Update the device registry with new information about the DMR."""
        if not self._device:
            return  # Can't get all the required information without a connection

        if not self.registry_entry or not self.registry_entry.config_entry_id:
            return  # No config registry entry to link to

        if self.registry_entry.device_id and not set_mac:
            return  # No new information

        connections = set()
        # Connections based on the root device's UDN, and the DMR embedded
        # device's UDN. They may be the same, if the DMR is the root device.
        connections.add(
            (
                device_registry.CONNECTION_UPNP,
                self._device.profile_device.root_device.udn,
            )
        )
        connections.add((device_registry.CONNECTION_UPNP, self._device.udn))

        if self.mac_address:
            # Connection based on MAC address, if known
            connections.add(
                # Device MAC is obtained from the config entry, which uses getmac
                (device_registry.CONNECTION_NETWORK_MAC, self.mac_address)
            )

        # Create linked HA DeviceEntry now the information is known.
        dev_reg = device_registry.async_get(self.hass)
        device_entry = dev_reg.async_get_or_create(
            config_entry_id=self.registry_entry.config_entry_id,
            connections=connections,
            identifiers={(DOMAIN, self.unique_id)},
            default_manufacturer=self._device.manufacturer,
            default_model=self._device.model_name,
            default_name=self._device.name,
        )

        # Update entity registry to link to the device
        ent_reg = entity_registry.async_get(self.hass)
        ent_reg.async_get_or_create(
            self.registry_entry.domain,
            self.registry_entry.platform,
            self.unique_id,
            device_id=device_entry.id,
        )

    async def _device_disconnect(self) -> None:
        """Destroy connections to the device now that it's not available.

        Also call when removing this entity from hass to clean up connections.
        """
        async with self._device_lock:
            if not self._device:
                _LOGGER.debug("Disconnecting from device that's not connected")
                return

            _LOGGER.debug("Disconnecting from %s", self._device.name)

            self._device.on_event = None
            old_device = self._device
            self._device = None
            await old_device.async_unsubscribe_services()

        domain_data = get_domain_data(self.hass)
        await domain_data.async_release_event_notifier(self._event_addr)

    async def async_update(self) -> None:
        """Retrieve the latest data."""
        if not self._device:
            if not self.poll_availability:
                return
            try:
                await self._device_connect(self.location)
            except UpnpError:
                return

        assert self._device is not None

        try:
            do_ping = self.poll_availability or self.check_available
            await self._device.async_update(do_ping=do_ping)
        except UpnpError as err:
            _LOGGER.debug("Device unavailable: %r", err)
            await self._device_disconnect()
            return
        finally:
            self.check_available = False

    def _on_event(
        self, service: UpnpService, state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        """State variable(s) changed, let home-assistant know."""
        if not state_variables:
            # Indicates a failure to resubscribe, check if device is still available
            self.check_available = True

        force_refresh = False

        if service.service_id == "urn:upnp-org:serviceId:AVTransport":
            for state_variable in state_variables:
                # Force a state refresh when player begins or pauses playback
                # to update the position info.
                if (
                    state_variable.name == "TransportState"
                    and state_variable.value
                    in (TransportState.PLAYING, TransportState.PAUSED_PLAYBACK)
                ):
                    force_refresh = True

        self.async_schedule_update_ha_state(force_refresh)

    @property
    def available(self) -> bool:
        """Device is available when we have a connection to it."""
        return self._device is not None and self._device.profile_device.available

    @property
    def unique_id(self) -> str:
        """Report the UDN (Unique Device Name) as this entity's unique ID."""
        return self.udn

    @property
    def usn(self) -> str:
        """Get the USN based on the UDN (Unique Device Name) and device type."""
        return f"{self.udn}::{self.device_type}"

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the player."""
        if not self._device or not self.available:
            return MediaPlayerState.OFF
        if self._device.transport_state is None:
            return MediaPlayerState.ON
        if self._device.transport_state in (
            TransportState.PLAYING,
            TransportState.TRANSITIONING,
        ):
            return MediaPlayerState.PLAYING
        if self._device.transport_state in (
            TransportState.PAUSED_PLAYBACK,
            TransportState.PAUSED_RECORDING,
        ):
            return MediaPlayerState.PAUSED
        if self._device.transport_state == TransportState.VENDOR_DEFINED:
            # Unable to map this state to anything reasonable, so it's "Unknown"
            return None

        return MediaPlayerState.IDLE

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported at this moment.

        Supported features may change as the device enters different states.
        """
        if not self._device:
            return MediaPlayerEntityFeature(0)

        supported_features = MediaPlayerEntityFeature(0)

        if self._device.has_volume_level:
            supported_features |= MediaPlayerEntityFeature.VOLUME_SET
        if self._device.has_volume_mute:
            supported_features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if self._device.can_play:
            supported_features |= MediaPlayerEntityFeature.PLAY
        if self._device.can_pause:
            supported_features |= MediaPlayerEntityFeature.PAUSE
        if self._device.can_stop:
            supported_features |= MediaPlayerEntityFeature.STOP
        if self._device.can_previous:
            supported_features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if self._device.can_next:
            supported_features |= MediaPlayerEntityFeature.NEXT_TRACK
        if self._device.has_play_media:
            supported_features |= (
                MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.BROWSE_MEDIA
            )
        if self._device.can_seek_rel_time:
            supported_features |= MediaPlayerEntityFeature.SEEK

        play_modes = self._device.valid_play_modes
        if play_modes & {PlayMode.RANDOM, PlayMode.SHUFFLE}:
            supported_features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if play_modes & {PlayMode.REPEAT_ONE, PlayMode.REPEAT_ALL}:
            supported_features |= MediaPlayerEntityFeature.REPEAT_SET

        if self._device.has_presets:
            supported_features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE

        return supported_features

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if not self._device or not self._device.has_volume_level:
            return None
        return self._device.volume_level

    @catch_request_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        assert self._device is not None
        await self._device.async_set_volume_level(volume)

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if not self._device:
            return None
        return self._device.is_volume_muted

    @catch_request_errors
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        assert self._device is not None
        desired_mute = bool(mute)
        await self._device.async_mute_volume(desired_mute)

    @catch_request_errors
    async def async_media_pause(self) -> None:
        """Send pause command."""
        assert self._device is not None
        await self._device.async_pause()

    @catch_request_errors
    async def async_media_play(self) -> None:
        """Send play command."""
        assert self._device is not None
        await self._device.async_play()

    @catch_request_errors
    async def async_media_stop(self) -> None:
        """Send stop command."""
        assert self._device is not None
        await self._device.async_stop()

    @catch_request_errors
    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        assert self._device is not None
        time = timedelta(seconds=position)
        await self._device.async_seek_rel_time(time)

    @catch_request_errors
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Playing media: %s, %s, %s", media_type, media_id, kwargs)
        assert self._device is not None

        didl_metadata: str | None = None
        title: str = ""

        # If media is media_source, resolve it to url and MIME type, and maybe metadata
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_type = sourced_media.mime_type
            media_id = sourced_media.url
            _LOGGER.debug("sourced_media is %s", sourced_media)
            if sourced_metadata := getattr(sourced_media, "didl_metadata", None):
                didl_metadata = didl_lite.to_xml_string(sourced_metadata).decode(
                    "utf-8"
                )
                title = sourced_metadata.title

        # If media ID is a relative URL, we serve it from HA.
        media_id = async_process_play_media_url(self.hass, media_id)

        extra: dict[str, Any] = kwargs.get(ATTR_MEDIA_EXTRA) or {}
        metadata: dict[str, Any] = extra.get("metadata") or {}

        if not title:
            title = extra.get("title") or metadata.get("title") or "Home Assistant"
        if thumb := extra.get("thumb"):
            metadata["album_art_uri"] = thumb

        # Translate metadata keys from HA names to DIDL-Lite names
        for hass_key, didl_key in MEDIA_METADATA_DIDL.items():
            if hass_key in metadata:
                metadata[didl_key] = metadata.pop(hass_key)

        if not didl_metadata:
            # Create metadata specific to the given media type; different fields are
            # available depending on what the upnp_class is.
            upnp_class = MEDIA_UPNP_CLASS_MAP.get(media_type)
            didl_metadata = await self._device.construct_play_media_metadata(
                media_url=media_id,
                media_title=title,
                override_upnp_class=upnp_class,
                meta_data=metadata,
            )

        # Stop current playing media
        if self._device.can_stop:
            await self.async_media_stop()

        # Queue media
        await self._device.async_set_transport_uri(media_id, title, didl_metadata)

        # If already playing, or don't want to autoplay, no need to call Play
        autoplay = extra.get("autoplay", True)
        if self._device.transport_state == TransportState.PLAYING or not autoplay:
            return

        # Play it
        await self._device.async_wait_for_can_play()
        await self.async_media_play()

    @catch_request_errors
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        assert self._device is not None
        await self._device.async_previous()

    @catch_request_errors
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        assert self._device is not None
        await self._device.async_next()

    @property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        if not self._device:
            return None

        if not (play_mode := self._device.play_mode):
            return None

        if play_mode == PlayMode.VENDOR_DEFINED:
            return None

        return play_mode in (PlayMode.SHUFFLE, PlayMode.RANDOM)

    @catch_request_errors
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        assert self._device is not None

        repeat = self.repeat or RepeatMode.OFF
        potential_play_modes = SHUFFLE_PLAY_MODES[(shuffle, repeat)]

        valid_play_modes = self._device.valid_play_modes

        for mode in potential_play_modes:
            if mode in valid_play_modes:
                await self._device.async_set_play_mode(mode)
                return

        _LOGGER.debug(
            "Couldn't find a suitable mode for shuffle=%s, repeat=%s", shuffle, repeat
        )

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if not self._device:
            return None

        if not (play_mode := self._device.play_mode):
            return None

        if play_mode == PlayMode.VENDOR_DEFINED:
            return None

        if play_mode == PlayMode.REPEAT_ONE:
            return RepeatMode.ONE

        if play_mode in (PlayMode.REPEAT_ALL, PlayMode.RANDOM):
            return RepeatMode.ALL

        return RepeatMode.OFF

    @catch_request_errors
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        assert self._device is not None

        shuffle = self.shuffle or False
        potential_play_modes = REPEAT_PLAY_MODES[(shuffle, repeat)]

        valid_play_modes = self._device.valid_play_modes

        for mode in potential_play_modes:
            if mode in valid_play_modes:
                await self._device.async_set_play_mode(mode)
                return

        _LOGGER.debug(
            "Couldn't find a suitable mode for shuffle=%s, repeat=%s", shuffle, repeat
        )

    @property
    def sound_mode(self) -> str | None:
        """Name of the current sound mode, not supported by DLNA."""
        return None

    @property
    def sound_mode_list(self) -> list[str] | None:
        """List of available sound modes."""
        if not self._device:
            return None
        return self._device.preset_names

    @catch_request_errors
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        assert self._device is not None
        await self._device.async_select_preset(sound_mode)

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper.

        Browses all available media_sources by default. Filters content_type
        based on the DMR's sink_protocol_info.
        """
        _LOGGER.debug(
            "async_browse_media(%s, %s)", media_content_type, media_content_id
        )

        # media_content_type is ignored; it's the content_type of the current
        # media_content_id, not the desired content_type of whomever is calling.

        if self.browse_unfiltered:
            content_filter = None
        else:
            content_filter = self._get_content_filter()

        return await media_source.async_browse_media(
            self.hass, media_content_id, content_filter=content_filter
        )

    def _get_content_filter(self) -> Callable[[BrowseMedia], bool]:
        """Return a function that filters media based on what the renderer can play.

        The filtering is pretty loose; it's better to show something that can't
        be played than hide something that can.
        """
        if not self._device or not self._device.sink_protocol_info:
            # Nothing is specified by the renderer, so show everything
            _LOGGER.debug("Get content filter with no device or sink protocol info")
            return lambda _: True

        _LOGGER.debug("Get content filter for %s", self._device.sink_protocol_info)
        if self._device.sink_protocol_info[0] == "*":
            # Renderer claims it can handle everything, so show everything
            return lambda _: True

        # Convert list of things like "http-get:*:audio/mpeg;codecs=mp3:*"
        # to just "audio/mpeg"
        content_types = set[str]()
        for protocol_info in self._device.sink_protocol_info:
            protocol, _, content_format, _ = protocol_info.split(":", 3)
            # Transform content_format for better generic matching
            content_format = content_format.lower().replace("/x-", "/", 1)
            content_format = content_format.partition(";")[0]

            if protocol in STREAMABLE_PROTOCOLS:
                content_types.add(content_format)

        def _content_filter(item: BrowseMedia) -> bool:
            """Filter media items by their media_content_type."""
            content_type = item.media_content_type
            content_type = content_type.lower().replace("/x-", "/", 1).partition(";")[0]
            return content_type in content_types

        return _content_filter

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if not self._device:
            return None
        # Use the best available title
        return self._device.media_program_title or self._device.media_title

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if not self._device:
            return None
        return self._device.media_image_url

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        if not self._device:
            return None
        return self._device.current_track_uri

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        if not self._device or not self._device.media_class:
            return None
        return MEDIA_TYPE_MAP.get(self._device.media_class)

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if not self._device:
            return None
        return self._device.media_duration

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if not self._device:
            return None
        return self._device.media_position

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        if not self._device:
            return None
        return self._device.media_position_updated_at

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if not self._device:
            return None
        return self._device.media_artist

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        if not self._device:
            return None
        return self._device.media_album_name

    @property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        if not self._device:
            return None
        return self._device.media_album_artist

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        if not self._device:
            return None
        return self._device.media_track_number

    @property
    def media_series_title(self) -> str | None:
        """Title of series of current playing media, TV show only."""
        if not self._device:
            return None
        return self._device.media_series_title

    @property
    def media_season(self) -> str | None:
        """Season number, starting at 1, of current playing media, TV show only."""
        if not self._device:
            return None
        # Some DMRs, like Kodi, leave this as 0 and encode the season & episode
        # in the episode_number metadata, as {season:d}{episode:02d}
        if (
            not self._device.media_season_number
            or self._device.media_season_number == "0"
        ) and self._device.media_episode_number:
            with contextlib.suppress(ValueError):
                episode = int(self._device.media_episode_number, 10)
                if episode > 100:
                    return str(episode // 100)
        return self._device.media_season_number

    @property
    def media_episode(self) -> str | None:
        """Episode number of current playing media, TV show only."""
        if not self._device:
            return None
        # Complement to media_season math above
        if (
            not self._device.media_season_number
            or self._device.media_season_number == "0"
        ) and self._device.media_episode_number:
            with contextlib.suppress(ValueError):
                episode = int(self._device.media_episode_number, 10)
                if episode > 100:
                    return str(episode % 100)
        return self._device.media_episode_number

    @property
    def media_channel(self) -> str | None:
        """Channel name currently playing."""
        if not self._device:
            return None
        return self._device.media_channel_name

    @property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        if not self._device:
            return None
        return self._device.media_playlist_title
