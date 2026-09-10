"""Support for interface with an Samsung TV."""

import asyncio
from typing import Any, override

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.async_ import create_eager_task

from .bridge import SamsungTVWSBridge
from .const import CONF_SSDP_RENDERING_CONTROL_LOCATION, DOMAIN, LOGGER
from .coordinator import SamsungTVConfigEntry, SamsungTVDataUpdateCoordinator
from .dmr import SamsungTVDmrDevice
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

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


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
            # Deprecated: Implicit Wake-On-LAN, will be removed in 2026.8.0
            # Triggers have not yet been registered so this is adjusted in the property
            self._attr_supported_features |= MediaPlayerEntityFeature.TURN_ON
        if self._ssdp_rendering_control_location:
            self._attr_supported_features |= MediaPlayerEntityFeature.VOLUME_SET

        self._dmr: SamsungTVDmrDevice | None = None

    @property
    @override
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

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        self._bridge.register_app_list_callback(self._app_list_callback)
        await self._async_extra_update()
        self.coordinator.async_extra_update = self._async_extra_update

        if self.coordinator.is_on:
            self._attr_state = MediaPlayerState.ON
            self._update_from_upnp()
        else:
            self._attr_state = MediaPlayerState.OFF

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Handle removal."""
        self.coordinator.async_extra_update = None
        if self._dmr:
            await self._dmr.async_shutdown()

    @callback
    @override
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
            if self._dmr and self._dmr.is_subscribed:
                await self._dmr.async_unsubscribe()
            return

        startup_tasks: list[asyncio.Task[Any]] = []

        if not self._app_list_event.is_set():
            startup_tasks.append(create_eager_task(self._async_startup_app_list()))

        if not self._dmr and self._ssdp_rendering_control_location:
            self._dmr = SamsungTVDmrDevice(
                hass=self.hass,
                ssdp_rendering_control_location=self._ssdp_rendering_control_location,
                host=self._host,
                on_event_callback=self._on_dmr_event_callback,
            )
        if self._dmr:
            if self._dmr.device and not self._dmr.is_subscribed:
                startup_tasks.append(create_eager_task(self._dmr.async_resubscribe()))
            elif not self._dmr.device:
                startup_tasks.append(create_eager_task(self._dmr.async_startup()))

        if startup_tasks:
            await asyncio.gather(*startup_tasks)

    @callback
    def _update_from_upnp(self) -> bool:
        # Upnp events can affect other attributes that we currently do not track
        # We want to avoid checking every attribute in 'async_write_ha_state' as we
        # currently only care about two attributes
        if self._dmr is None:
            return False

        has_updates = False

        if (
            volume_level := self._dmr.volume_level
        ) is not None and self._attr_volume_level != volume_level:
            self._attr_volume_level = volume_level
            has_updates = True

        if (
            is_muted := self._dmr.is_volume_muted
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

    @callback
    def _on_dmr_event_callback(self) -> None:
        """Handle UPnP state variable changes from DMR device."""
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

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level on the media player."""
        if self._dmr is None:
            LOGGER.warning("Upnp services are not available on %s", self._host)
            return
        await self._dmr.async_set_volume_level(volume)

    @override
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._async_send_keys(["KEY_VOLUP"])

    @override
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._async_send_keys(["KEY_VOLDOWN"])

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._async_send_keys(["KEY_MUTE"])

    @override
    async def async_media_play_pause(self) -> None:
        """Simulate play pause media player."""
        if self._playing:
            await self.async_media_pause()
        else:
            await self.async_media_play()

    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        self._playing = True
        await self._async_send_keys(["KEY_PLAY"])

    @override
    async def async_media_pause(self) -> None:
        """Send media pause command to media player."""
        self._playing = False
        await self._async_send_keys(["KEY_PAUSE"])

    @override
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._async_send_keys(["KEY_CHUP"])

    @override
    async def async_media_previous_track(self) -> None:
        """Send the previous track command."""
        await self._async_send_keys(["KEY_CHDOWN"])

    @override
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
        except vol.Invalid as err:
            LOGGER.error("Media ID must be positive integer")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="media_id_invalid",
            ) from err

        await self._async_send_keys(
            keys=[f"KEY_{digit}" for digit in media_id] + ["KEY_ENTER"]
        )

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if self._app_list and source in self._app_list:
            await self._async_launch_app(self._app_list[source])
            return

        if source in SOURCES:
            await self._async_send_keys([SOURCES[source]])
            return

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="source_unsupported",
            translation_placeholders={"entity": self.entity_id, "source": source},
        )
