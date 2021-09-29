"""Support for DLNA DMR (Device Media Renderer)."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
import functools
from typing import Any, Callable, TypeVar, cast

from async_upnp_client import UpnpError, UpnpService, UpnpStateVariable
from async_upnp_client.const import NotificationSubType
from async_upnp_client.profiles.dlna import DmrDevice, TransportState
from async_upnp_client.utils import async_get_local_ip
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_TYPE,
    CONF_URL,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER as _LOGGER,
    MEDIA_TYPE_MAP,
)
from .data import EventListenAddr, get_domain_data

PARALLEL_UPDATES = 0

# Configuration via YAML is deprecated in favour of config flow
CONF_LISTEN_IP = "listen_ip"
PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_URL),
    cv.deprecated(CONF_LISTEN_IP),
    cv.deprecated(CONF_LISTEN_PORT),
    cv.deprecated(CONF_NAME),
    cv.deprecated(CONF_CALLBACK_URL_OVERRIDE),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_URL): cv.string,
            vol.Optional(CONF_LISTEN_IP): cv.string,
            vol.Optional(CONF_LISTEN_PORT): cv.port,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_CALLBACK_URL_OVERRIDE): cv.url,
        }
    ),
)

Func = TypeVar("Func", bound=Callable[..., Any])


def catch_request_errors(func: Func) -> Func:
    """Catch UpnpError errors."""

    @functools.wraps(func)
    async def wrapper(self: "DlnaDmrEntity", *args: Any, **kwargs: Any) -> Any:
        """Catch UpnpError errors and check availability before and after request."""
        if not self.available:
            _LOGGER.warning(
                "Device disappeared when trying to call service %s", func.__name__
            )
            return
        try:
            return await func(self, *args, **kwargs)
        except UpnpError as err:
            self.check_available = True
            _LOGGER.error("Error during call %s: %r", func.__name__, err)

    return cast(Func, wrapper)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DlnaDmrEntity from a config entry."""
    del hass  # Unused
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
    )

    entry.async_on_unload(
        entry.add_update_listener(entity.async_config_update_listener)
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

    _device_lock: asyncio.Lock  # Held when connecting or disconnecting the device
    _device: DmrDevice | None = None
    _remove_ssdp_callbacks: list[Callable]
    check_available: bool = False

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
    ) -> None:
        """Initialize DLNA DMR entity."""
        self.udn = udn
        self.device_type = device_type
        self._attr_name = name
        self._event_addr = EventListenAddr(None, event_port, event_callback_url)
        self.poll_availability = poll_availability
        self.location = location
        self._device_lock = asyncio.Lock()
        self._remove_ssdp_callbacks = []

    async def async_added_to_hass(self) -> None:
        """Handle addition."""
        # Try to connect to the last known location, but don't worry if not available
        if not self._device:
            try:
                await self._device_connect(self.location)
            except UpnpError as err:
                _LOGGER.debug("Couldn't connect immediately: %r", err)

        # Get SSDP notifications for only this device
        self._remove_ssdp_callbacks.append(
            await ssdp.async_register_callback(
                self.hass, self.async_ssdp_callback, {"USN": self.usn}
            )
        )

        # async_upnp_client.SsdpListener only reports byebye once for each *UDN*
        # (device name) which often is not the USN (service within the device)
        # that we're interested in. So also listen for byebye advertisements for
        # the UDN, which is reported in the _udn field of the combined_headers.
        self._remove_ssdp_callbacks.append(
            await ssdp.async_register_callback(
                self.hass,
                self.async_ssdp_callback,
                {"_udn": self.udn, "NTS": NotificationSubType.SSDP_BYEBYE},
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal."""
        for callback in self._remove_ssdp_callbacks:
            callback()
        self._remove_ssdp_callbacks.clear()
        await self._device_disconnect()

    async def async_ssdp_callback(
        self, info: Mapping[str, Any], change: ssdp.SsdpChange
    ) -> None:
        """Handle notification from SSDP of device state change."""
        _LOGGER.debug(
            "SSDP %s notification of device %s at %s",
            change,
            info[ssdp.ATTR_SSDP_USN],
            info.get(ssdp.ATTR_SSDP_LOCATION),
        )

        try:
            bootid_str = info[ssdp.ATTR_SSDP_BOOTID]
            bootid: int | None = int(bootid_str, 10)
        except (KeyError, ValueError):
            bootid = None

        if change == ssdp.SsdpChange.UPDATE:
            # This is an announcement that bootid is about to change
            if self._bootid is not None and self._bootid == bootid:
                # Store the new value (because our old value matches) so that we
                # can ignore subsequent ssdp:alive messages
                try:
                    next_bootid_str = info[ssdp.ATTR_SSDP_NEXTBOOTID]
                    self._bootid = int(next_bootid_str, 10)
                except (KeyError, ValueError):
                    pass
            # Nothing left to do until ssdp:alive comes through
            return

        if self._bootid is not None and self._bootid != bootid and self._device:
            # Device has rebooted, drop existing connection and maybe reconnect
            await self._device_disconnect()
        self._bootid = bootid

        if change == ssdp.SsdpChange.BYEBYE and self._device:
            # Device is going away, disconnect
            await self._device_disconnect()

        if change == ssdp.SsdpChange.ALIVE and not self._device:
            location = info[ssdp.ATTR_SSDP_LOCATION]
            try:
                await self._device_connect(location)
            except UpnpError as err:
                _LOGGER.warning(
                    "Failed connecting to recently alive device at %s: %r",
                    location,
                    err,
                )

        # Device could have been de/re-connected, state probably changed
        self.schedule_update_ha_state()

    async def async_config_update_listener(
        self, hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> None:
        """Handle options update by modifying self in-place."""
        del hass  # Unused
        _LOGGER.debug(
            "Updating: %s with data=%s and options=%s",
            self.name,
            entry.data,
            entry.options,
        )
        self.location = entry.data[CONF_URL]
        self.poll_availability = entry.options.get(CONF_POLL_AVAILABILITY, False)

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
        self.schedule_update_ha_state()

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
            except UpnpError as err:
                # Don't leave the device half-constructed
                self._device.on_event = None
                self._device = None
                await domain_data.async_release_event_notifier(self._event_addr)
                _LOGGER.debug("Error while subscribing during device connect: %r", err)
                raise

        if (
            not self.registry_entry
            or not self.registry_entry.config_entry_id
            or self.registry_entry.device_id
        ):
            return

        # Create linked HA DeviceEntry now the information is known.
        dev_reg = device_registry.async_get(self.hass)
        device_entry = dev_reg.async_get_or_create(
            config_entry_id=self.registry_entry.config_entry_id,
            # Connections are based on the root device's UDN, and the DMR
            # embedded device's UDN. They may be the same, if the DMR is the
            # root device.
            connections={
                (
                    device_registry.CONNECTION_UPNP,
                    self._device.profile_device.root_device.udn,
                ),
                (device_registry.CONNECTION_UPNP, self._device.udn),
            },
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
        except UpnpError:
            _LOGGER.debug("Device unavailable")
            await self._device_disconnect()
            return
        finally:
            self.check_available = False

    def _on_event(
        self, service: UpnpService, state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        """State variable(s) changed, let home-assistant know."""
        del service  # Unused
        if not state_variables:
            # Indicates a failure to resubscribe, check if device is still available
            self.check_available = True
        self.schedule_update_ha_state()

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
    def state(self) -> str | None:
        """State of the player."""
        if not self._device or not self.available:
            return STATE_OFF
        if self._device.transport_state is None:
            return STATE_ON
        if self._device.transport_state in (
            TransportState.PLAYING,
            TransportState.TRANSITIONING,
        ):
            return STATE_PLAYING
        if self._device.transport_state in (
            TransportState.PAUSED_PLAYBACK,
            TransportState.PAUSED_RECORDING,
        ):
            return STATE_PAUSED
        if self._device.transport_state == TransportState.VENDOR_DEFINED:
            # Unable to map this state to anything reasonable, so it's "Unknown"
            return None

        return STATE_IDLE

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported at this moment.

        Supported features may change as the device enters different states.
        """
        if not self._device:
            return 0

        supported_features = 0

        if self._device.has_volume_level:
            supported_features |= SUPPORT_VOLUME_SET
        if self._device.has_volume_mute:
            supported_features |= SUPPORT_VOLUME_MUTE
        if self._device.can_play:
            supported_features |= SUPPORT_PLAY
        if self._device.can_pause:
            supported_features |= SUPPORT_PAUSE
        if self._device.can_stop:
            supported_features |= SUPPORT_STOP
        if self._device.can_previous:
            supported_features |= SUPPORT_PREVIOUS_TRACK
        if self._device.can_next:
            supported_features |= SUPPORT_NEXT_TRACK
        if self._device.has_play_media:
            supported_features |= SUPPORT_PLAY_MEDIA
        if self._device.can_seek_rel_time:
            supported_features |= SUPPORT_SEEK

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
    async def async_media_seek(self, position: int | float) -> None:
        """Send seek command."""
        assert self._device is not None
        time = timedelta(seconds=position)
        await self._device.async_seek_rel_time(time)

    @catch_request_errors
    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Playing media: %s, %s, %s", media_type, media_id, kwargs)
        title = "Home Assistant"

        assert self._device is not None

        # Stop current playing media
        if self._device.can_stop:
            await self.async_media_stop()

        # Queue media
        await self._device.async_set_transport_uri(media_id, title)
        await self._device.async_wait_for_can_play()

        # If already playing, no need to call Play
        if self._device.transport_state == TransportState.PLAYING:
            return

        # Play it
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
    def media_content_type(self) -> str | None:
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
            try:
                episode = int(self._device.media_episode_number, 10)
                if episode > 100:
                    return str(episode // 100)
            except ValueError:
                pass
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
            try:
                episode = int(self._device.media_episode_number, 10)
                if episode > 100:
                    return str(episode % 100)
            except ValueError:
                pass
        return self._device.media_episode_number

    @property
    def media_channel(self) -> str | None:
        """Channel name currently playing."""
        if not self._device:
            return None
        return self._device.media_channel_name
