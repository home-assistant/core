"""Support for DLNA DMR (Device Media Renderer)."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime, timedelta
import functools
from typing import Any, Callable, TypeVar, cast

from async_upnp_client import UpnpError, UpnpService, UpnpStateVariable
from async_upnp_client.profiles.dlna import DeviceState, DmrDevice
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
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_UPNP
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    LOGGER as _LOGGER,
)
from .data import EventListenAddr, get_domain_data

# Configuration via YAML is deprecated in favour of config flow
CONF_LISTEN_IP = "listen_ip"
DEFAULT_NAME = "DLNA Digital Media Renderer"
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
        """Catch UpnpError errors and check availability."""
        try:
            return await func(self, *args, **kwargs)
        except UpnpError as err:
            self.check_available = True
            _LOGGER.error("Error during call %s: %s(%s)", func.__name__, type(err), err)

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
    event_addr = EventListenAddr(
        entry.options.get(CONF_LISTEN_PORT) or 0,
        entry.options.get(CONF_CALLBACK_URL_OVERRIDE),
    )
    entity = DlnaDmrEntity(
        udn=entry.data[CONF_DEVICE_ID],
        device_type=entry.data[CONF_TYPE],
        name=entry.title,
        event_addr=event_addr,
        poll_availability=entry.options.get(CONF_POLL_AVAILABILITY, False),
        location=entry.data[CONF_URL],
    )

    entry.async_on_unload(
        entry.add_update_listener(entity.async_config_update_listener)
    )

    async_add_entities([entity], True)


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
    _ssdp_callback: Callable | None = None
    check_available: bool = False

    # DMR devices need polling for track position information. async_update will
    # determine whether further device polling is required.
    _attr_should_poll = True

    def __init__(
        self,
        udn: str,
        device_type: str,
        name: str,
        event_addr: EventListenAddr,
        poll_availability: bool,
        location: str,
    ) -> None:
        """Initialize DLNA DMR entity."""
        self.udn = udn
        self.device_type = device_type
        self._attr_name = name
        self._event_addr = event_addr
        self.poll_availability = poll_availability
        self.location = location
        self._device_lock = asyncio.Lock()

    async def async_added_to_hass(self) -> None:
        """Handle addition."""
        # Try to connect to the last known location, but don't worry if not available
        if not self._device:
            try:
                await self._device_connect(self.location)
            except UpnpError as err:
                _LOGGER.debug("Couldn't connect immediately: %s", err)

        # Get SSDP notifications for only this device
        self._ssdp_callback = ssdp.async_register_callback(
            self.hass, self._async_ssdp_notified, {"USN": self.usn}
        )

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal."""
        if self._ssdp_callback:
            self._ssdp_callback()
        await self._device_disconnect()

    @callback
    def _async_ssdp_notified(self, info: dict[str, str]) -> None:
        """Handle notification from SSDP of device state change."""
        _LOGGER.debug(
            "SSDP notification of device %s at %s",
            info[ssdp.ATTR_SSDP_USN],
            info[ssdp.ATTR_SSDP_LOCATION],
        )

        if not self._device:
            location = info[ssdp.ATTR_SSDP_LOCATION]
            self.hass.async_run_job(self._device_connect, location)

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

        new_event_addr = EventListenAddr(
            entry.options.get(CONF_LISTEN_PORT) or 0,
            entry.options.get(CONF_CALLBACK_URL_OVERRIDE),
        )
        if new_event_addr != self._event_addr:
            self._event_addr = new_event_addr
            # Changes to eventing requires a device reconnect for it to update correctly
            await self._device_disconnect()
            try:
                await self._device_connect(self.location)
            except UpnpError as err:
                _LOGGER.debug("Couldn't (re)connect: %s", err)

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

            # Create/get event handler that is reachable by the device
            event_handler = await domain_data.async_get_event_notifier(
                self._event_addr, self.hass.loop
            )

            # Create profile wrapper
            self._device = DmrDevice(upnp_device, event_handler)

            # Set hass device information now that it's known.
            self._attr_device_info = {
                "name": self._device.name,
                # Connection is based on the root device's UDN, which is
                # currently equivalent to our UDN (embedded devices aren't
                # supported by async_upnp_client)
                "connections": {(CONNECTION_UPNP, self._device.udn)},
                "manufacturer": self._device.manufacturer,
                "model": self._device.model_name,
            }

            self.location = location

            # Subscribe to event notifications
            try:
                self._device.on_event = self._on_event
                await self._device.async_subscribe_services(auto_resubscribe=True)
            except UpnpError as err:
                # Don't leave the device half-constructed
                self._device = None
                _LOGGER.debug("Error while subscribing during device connect: %s", err)
                raise

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

    @property
    def available(self) -> bool:
        """Device is available when we have a connection to it."""
        return self._device is not None and self._device.device.available

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
            await self._device.async_update()
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
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        if not self._device:
            return 0

        supported_features = 0

        if self._device.has_volume_level:
            supported_features |= SUPPORT_VOLUME_SET
        if self._device.has_volume_mute:
            supported_features |= SUPPORT_VOLUME_MUTE
        if self._device.has_play:
            supported_features |= SUPPORT_PLAY
        if self._device.has_pause:
            supported_features |= SUPPORT_PAUSE
        if self._device.has_stop:
            supported_features |= SUPPORT_STOP
        if self._device.has_previous:
            supported_features |= SUPPORT_PREVIOUS_TRACK
        if self._device.has_next:
            supported_features |= SUPPORT_NEXT_TRACK
        if self._device.has_play_media:
            supported_features |= SUPPORT_PLAY_MEDIA
        if self._device.has_seek_rel_time:
            supported_features |= SUPPORT_SEEK

        return supported_features

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if (
            not self._device
            or not self._device.has_volume_level
            or self._device.volume_level is None
        ):
            _LOGGER.debug("Cannot get volume level")
            return None
        return self._device.volume_level

    @catch_request_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        if not self._device or not self._device.has_volume_level:
            _LOGGER.debug("Cannot set volume level")
            return
        await self._device.async_set_volume_level(volume)

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if not self._device or not self._device.has_volume_mute:
            _LOGGER.debug("Cannot get volume mute")
            return None
        return self._device.is_volume_muted

    @catch_request_errors
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if not self._device or not self._device.has_volume_mute:
            _LOGGER.debug("Cannot set volume mute")
            return

        desired_mute = bool(mute)
        await self._device.async_mute_volume(desired_mute)

    @catch_request_errors
    async def async_media_pause(self) -> None:
        """Send pause command."""
        if not self._device or not self._device.can_pause:
            _LOGGER.debug("Cannot do Pause")
            return

        await self._device.async_pause()

    @catch_request_errors
    async def async_media_play(self) -> None:
        """Send play command."""
        if not self._device or not self._device.can_play:
            _LOGGER.debug("Cannot do Play")
            return

        await self._device.async_play()

    @catch_request_errors
    async def async_media_stop(self) -> None:
        """Send stop command."""
        if not self._device or not self._device.can_stop:
            _LOGGER.debug("Cannot do Stop")
            return

        await self._device.async_stop()

    @catch_request_errors
    async def async_media_seek(self, position: int | float) -> None:
        """Send seek command."""
        if not self._device or not self._device.can_seek_rel_time:
            _LOGGER.debug("Cannot do Seek/rel_time")
            return

        time = timedelta(seconds=position)
        await self._device.async_seek_rel_time(time)

    @catch_request_errors
    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Playing media: %s, %s, %s", media_type, media_id, kwargs)
        title = "Home Assistant"

        if not self._device or not self._device.has_play_media:
            _LOGGER.debug("Cannot do play / set_transport_uri")
            return

        # Stop current playing media
        if self._device.can_stop:
            await self.async_media_stop()

        # Queue media
        await self._device.async_set_transport_uri(media_id, title)
        await self._device.async_wait_for_can_play()

        # If already playing, no need to call Play
        if self._device.state == DeviceState.PLAYING:
            return

        # Play it
        await self.async_media_play()

    @catch_request_errors
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if not self._device or not self._device.can_previous:
            _LOGGER.debug("Cannot do Previous")
            return

        await self._device.async_previous()

    @catch_request_errors
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if not self._device or not self._device.can_next:
            _LOGGER.debug("Cannot do Next")
            return

        await self._device.async_next()

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if not self._device:
            return None
        return self._device.media_title

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if not self._device:
            return None
        return self._device.media_image_url

    @property
    def state(self) -> str:
        """State of the player."""
        if not self._device or not self.available:
            return STATE_OFF

        if self._device.state == DeviceState.ON:
            return STATE_ON
        if self._device.state == DeviceState.PLAYING:
            return STATE_PLAYING
        if self._device.state == DeviceState.PAUSED:
            return STATE_PAUSED

        return STATE_IDLE

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
    def unique_id(self) -> str:
        """Report the UDN (Unique Device Name) as this entity's unique ID."""
        return self.udn

    @property
    def usn(self) -> str:
        """Get the USN based on the UDN (Unique Device Name) and device type."""
        return f"{self.udn}::{self.device_type}"
