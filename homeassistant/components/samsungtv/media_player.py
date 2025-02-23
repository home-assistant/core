"""Support for interface with an Samsung TV."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpSessionRequester
from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import (
    UpnpActionResponseError,
    UpnpCommunicationError,
    UpnpConnectionError,
    UpnpError,
    UpnpResponseError,
    UpnpXmlContentError,
)
from async_upnp_client.profiles.dlna import DmrDevice
from async_upnp_client.utils import async_get_local_ip
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.async_ import create_eager_task

from .bridge import SamsungTVWSBridge
from .const import CONF_SSDP_RENDERING_CONTROL_LOCATION, LOGGER
from .coordinator import SamsungTVConfigEntry, SamsungTVDataUpdateCoordinator
from .entity import SamsungTVEntity

SOURCES = {"TV": "KEY_TV", "HDMI": "KEY_HDMI"}

SUPPORT_SAMSUNGTV = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)


# Max delay waiting for app_list to return, as some TVs simply ignore the request
APP_LIST_DELAY = 3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SamsungTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Samsung TV from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([SamsungTVDevice(coordinator)])


class SamsungTVDevice(SamsungTVEntity, MediaPlayerEntity):
    """Representation of a Samsung TV."""

    _attr_source_list: list[str]
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(self, coordinator: SamsungTVDataUpdateCoordinator) -> None:
        """Initialize the Samsung device."""
        super().__init__(coordinator=coordinator)
        self._ssdp_rendering_control_location: str | None = (
            coordinator.config_entry.data.get(CONF_SSDP_RENDERING_CONTROL_LOCATION)
        )
        # Assume that the TV is in Play mode
        self._playing: bool = True

        self._attr_is_volume_muted: bool = False
        self._attr_source_list = list(SOURCES)
        self._app_list: dict[str, str] | None = None
        self._app_list_event: asyncio.Event = asyncio.Event()

        self._attr_supported_features = SUPPORT_SAMSUNGTV
        if self._mac:
            # (deprecated) add turn-on if mac is available
            # Triggers have not yet been registered so this is adjusted in the property
            self._attr_supported_features |= MediaPlayerEntityFeature.TURN_ON
        if self._ssdp_rendering_control_location:
            self._attr_supported_features |= MediaPlayerEntityFeature.VOLUME_SET

        self._bridge.register_app_list_callback(self._app_list_callback)

        self._dmr_device: DmrDevice | None = None
        self._upnp_server: AiohttpNotifyServer | None = None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        # `turn_on` triggers are not yet registered during initialisation,
        # so this property needs to be dynamic
        if self._turn_on_action:
            return self._attr_supported_features | MediaPlayerEntityFeature.TURN_ON
        return self._attr_supported_features

    def _update_sources(self) -> None:
        self._attr_source_list = list(SOURCES)
        if app_list := self._app_list:
            self._attr_source_list.extend(app_list)

    def _app_list_callback(self, app_list: dict[str, str]) -> None:
        """App list callback."""
        self._app_list = app_list
        self._update_sources()
        self._app_list_event.set()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self._async_extra_update()
        self.coordinator.async_extra_update = self._async_extra_update
        if self.coordinator.is_on:
            self._attr_state = MediaPlayerState.ON
            self._update_from_upnp()
        else:
            self._attr_state = MediaPlayerState.OFF

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal."""
        self.coordinator.async_extra_update = None
        await self._async_shutdown_dmr()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        if self.coordinator.is_on:
            self._attr_state = MediaPlayerState.ON
            self._update_from_upnp()
        else:
            self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def _async_extra_update(self) -> None:
        """Update state of device."""
        if not self.coordinator.is_on:
            if self._dmr_device and self._dmr_device.is_subscribed:
                await self._dmr_device.async_unsubscribe_services()
            return

        startup_tasks: list[asyncio.Task[Any]] = []

        if not self._app_list_event.is_set():
            startup_tasks.append(create_eager_task(self._async_startup_app_list()))

        if self._dmr_device and not self._dmr_device.is_subscribed:
            startup_tasks.append(create_eager_task(self._async_resubscribe_dmr()))
        if not self._dmr_device and self._ssdp_rendering_control_location:
            startup_tasks.append(create_eager_task(self._async_startup_dmr()))

        if startup_tasks:
            await asyncio.gather(*startup_tasks)

    @callback
    def _update_from_upnp(self) -> bool:
        # Upnp events can affect other attributes that we currently do not track
        # We want to avoid checking every attribute in 'async_write_ha_state' as we
        # currently only care about two attributes
        if (dmr_device := self._dmr_device) is None:
            return False

        has_updates = False

        if (
            volume_level := dmr_device.volume_level
        ) is not None and self._attr_volume_level != volume_level:
            self._attr_volume_level = volume_level
            has_updates = True

        if (
            is_muted := dmr_device.is_volume_muted
        ) is not None and self._attr_is_volume_muted != is_muted:
            self._attr_is_volume_muted = is_muted
            has_updates = True

        return has_updates

    async def _async_startup_app_list(self) -> None:
        await self._bridge.async_request_app_list()
        if self._app_list_event.is_set():
            # The try+wait_for is a bit expensive so we should try not to
            # enter it unless we have to (Python 3.11 will have zero cost try)
            return
        try:
            async with asyncio.timeout(APP_LIST_DELAY):
                await self._app_list_event.wait()
        except TimeoutError as err:
            # No need to try again
            self._app_list_event.set()
            LOGGER.debug("Failed to load app list from %s: %r", self._host, err)

    async def _async_startup_dmr(self) -> None:
        assert self._ssdp_rendering_control_location is not None
        if self._dmr_device is None:
            session = async_get_clientsession(self.hass)
            upnp_requester = AiohttpSessionRequester(session)
            # Set non_strict to avoid invalid data sent by Samsung TV:
            # Got invalid value for <UpnpStateVariable(PlaybackStorageMedium, string)>:
            # NETWORK,NONE
            upnp_factory = UpnpFactory(upnp_requester, non_strict=True)
            upnp_device: UpnpDevice | None = None
            try:
                upnp_device = await upnp_factory.async_create_device(
                    self._ssdp_rendering_control_location
                )
            except (UpnpConnectionError, UpnpResponseError, UpnpXmlContentError) as err:
                LOGGER.debug("Unable to create Upnp DMR device: %r", err, exc_info=True)
                return
            _, event_ip = await async_get_local_ip(
                self._ssdp_rendering_control_location, self.hass.loop
            )
            source = (event_ip or "0.0.0.0", 0)
            self._upnp_server = AiohttpNotifyServer(
                requester=upnp_requester,
                source=source,
                callback_url=None,
                loop=self.hass.loop,
            )
            await self._upnp_server.async_start_server()
            self._dmr_device = DmrDevice(upnp_device, self._upnp_server.event_handler)

            try:
                self._dmr_device.on_event = self._on_upnp_event
                await self._dmr_device.async_subscribe_services(auto_resubscribe=True)
            except UpnpResponseError as err:
                # Device rejected subscription request. This is OK, variables
                # will be polled instead.
                LOGGER.debug("Device rejected subscription: %r", err)
            except UpnpError as err:
                # Don't leave the device half-constructed
                self._dmr_device.on_event = None
                self._dmr_device = None
                await self._upnp_server.async_stop_server()
                self._upnp_server = None
                LOGGER.debug("Error while subscribing during device connect: %r", err)
                raise

    async def _async_resubscribe_dmr(self) -> None:
        assert self._dmr_device
        try:
            await self._dmr_device.async_subscribe_services(auto_resubscribe=True)
        except UpnpCommunicationError as err:
            LOGGER.debug("Device rejected re-subscription: %r", err, exc_info=True)

    async def _async_shutdown_dmr(self) -> None:
        """Handle removal."""
        if (dmr_device := self._dmr_device) is not None:
            self._dmr_device = None
            dmr_device.on_event = None
            await dmr_device.async_unsubscribe_services()

        if (upnp_server := self._upnp_server) is not None:
            self._upnp_server = None
            await upnp_server.async_stop_server()

    def _on_upnp_event(
        self, service: UpnpService, state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        """State variable(s) changed, let home-assistant know."""
        # Ensure the entity has been added to hass to avoid race condition
        if self._update_from_upnp() and self.entity_id:
            self.async_write_ha_state()

    async def _async_launch_app(self, app_id: str) -> None:
        """Send launch_app to the tv."""
        if self._bridge.power_off_in_progress:
            LOGGER.debug("TV is powering off, not sending launch_app command")
            return
        assert isinstance(self._bridge, SamsungTVWSBridge)
        await self._bridge.async_launch_app(app_id)

    async def _async_send_keys(self, keys: list[str]) -> None:
        """Send a key to the tv and handles exceptions."""
        assert keys
        if self._bridge.power_off_in_progress and keys[0] != "KEY_POWEROFF":
            LOGGER.debug("TV is powering off, not sending keys: %s", keys)
            return
        await self._bridge.async_send_keys(keys)

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await super()._async_turn_off()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level on the media player."""
        if (dmr_device := self._dmr_device) is None:
            LOGGER.warning("Upnp services are not available on %s", self._host)
            return
        try:
            await dmr_device.async_set_volume_level(volume)
        except UpnpActionResponseError as err:
            LOGGER.warning("Unable to set volume level on %s: %r", self._host, err)

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._async_send_keys(["KEY_VOLUP"])

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._async_send_keys(["KEY_VOLDOWN"])

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._async_send_keys(["KEY_MUTE"])

    async def async_media_play_pause(self) -> None:
        """Simulate play pause media player."""
        if self._playing:
            await self.async_media_pause()
        else:
            await self.async_media_play()

    async def async_media_play(self) -> None:
        """Send play command."""
        self._playing = True
        await self._async_send_keys(["KEY_PLAY"])

    async def async_media_pause(self) -> None:
        """Send media pause command to media player."""
        self._playing = False
        await self._async_send_keys(["KEY_PAUSE"])

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._async_send_keys(["KEY_CHUP"])

    async def async_media_previous_track(self) -> None:
        """Send the previous track command."""
        await self._async_send_keys(["KEY_CHDOWN"])

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Support changing a channel."""
        if media_type == MediaType.APP:
            await self._async_launch_app(media_id)
            return

        if media_type != MediaType.CHANNEL:
            LOGGER.error("Unsupported media type")
            return

        # media_id should only be a channel number
        try:
            cv.positive_int(media_id)
        except vol.Invalid:
            LOGGER.error("Media ID must be positive integer")
            return

        await self._async_send_keys(
            keys=[f"KEY_{digit}" for digit in media_id] + ["KEY_ENTER"]
        )

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await super()._async_turn_on()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if self._app_list and source in self._app_list:
            await self._async_launch_app(self._app_list[source])
            return

        if source in SOURCES:
            await self._async_send_keys([SOURCES[source]])
            return

        LOGGER.error("Unsupported source")
