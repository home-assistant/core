"""Support for PlayStation 4 consoles."""
import asyncio
from contextlib import suppress
import logging
from typing import Any, cast

from pyps4_2ndscreen.errors import NotReady, PSDataIncomplete
from pyps4_2ndscreen.media_art import TYPE_APP as PS_TYPE_APP
import pyps4_2ndscreen.ps4 as pyps4

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LOCKED,
    CONF_HOST,
    CONF_NAME,
    CONF_REGION,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.json import JsonObjectType

from . import format_unique_id, load_games, save_games
from .const import (
    ATTR_MEDIA_IMAGE_URL,
    DEFAULT_ALIAS,
    DOMAIN as PS4_DOMAIN,
    PS4_DATA,
    REGIONS as deprecated_regions,
)

_LOGGER = logging.getLogger(__name__)


ICON = "mdi:sony-playstation"

DEFAULT_RETRIES = 2


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PS4 from a config entry."""
    config = config_entry
    creds: str = config.data[CONF_TOKEN]
    device_list = []
    for device in config.data["devices"]:
        host: str = device[CONF_HOST]
        region: str = device[CONF_REGION]
        name: str = device[CONF_NAME]
        ps4 = pyps4.Ps4Async(host, creds, device_name=DEFAULT_ALIAS)
        device_list.append(PS4Device(config, name, host, region, ps4, creds))
    async_add_entities(device_list, update_before_add=True)


class PS4Device(MediaPlayerEntity):
    """Representation of a PS4."""

    _attr_icon = ICON
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(
        self,
        config: ConfigEntry,
        name: str,
        host: str,
        region: str,
        ps4: pyps4.Ps4Async,
        creds: str,
    ) -> None:
        """Initialize the ps4 device."""
        self._entry_id = config.entry_id
        self._ps4 = ps4
        self._host = host
        self._attr_name = name
        self._region = region
        self._creds = creds
        self._media_image: str | None = None
        self._games: JsonObjectType = {}
        self._retry = 0
        self._disconnected = False

    @callback
    def status_callback(self) -> None:
        """Handle status callback. Parse status."""
        self._parse_status()
        self.async_write_ha_state()

    @callback
    def subscribe_to_protocol(self) -> None:
        """Notify protocol to callback with update changes."""
        self.hass.data[PS4_DATA].protocol.add_callback(self._ps4, self.status_callback)

    @callback
    def unsubscribe_to_protocol(self) -> None:
        """Notify protocol to remove callback."""
        self.hass.data[PS4_DATA].protocol.remove_callback(
            self._ps4, self.status_callback
        )

    def check_region(self) -> None:
        """Display logger msg if region is deprecated."""
        # Non-Breaking although data returned may be inaccurate.
        if self._region in deprecated_regions:
            _LOGGER.info(
                """Region: %s has been deprecated.
                            Please remove PS4 integration
                            and Re-configure again to utilize
                            current regions""",
                self._region,
            )

    async def async_added_to_hass(self) -> None:
        """Subscribe PS4 events."""
        self.hass.data[PS4_DATA].devices.append(self)
        self.check_region()

    async def async_update(self) -> None:
        """Retrieve the latest data."""
        if self._ps4.ddp_protocol is not None:
            # Request Status with asyncio transport.
            self._ps4.get_status()

            # Don't attempt to connect if entity is connected or if,
            # PS4 is in standby or disconnected from LAN or powered off.
            if (
                not self._ps4.connected
                and not self._ps4.is_standby
                and self._ps4.is_available
            ):
                with suppress(NotReady):
                    await self._ps4.async_connect()

        # Try to ensure correct status is set on startup for device info.
        if self._ps4.ddp_protocol is None:
            # Use socket.socket.
            await self.hass.async_add_executor_job(self._ps4.get_status)
            if self._attr_device_info is None:
                # Add entity to registry.
                await self.async_get_device_info(self._ps4.status)
            self._ps4.ddp_protocol = self.hass.data[PS4_DATA].protocol
            self.subscribe_to_protocol()

        self._parse_status()

    def _parse_status(self) -> None:
        """Parse status."""
        status: dict[str, Any] | None = self._ps4.status
        if status is not None:
            self._games = load_games(self.hass, cast(str, self.unique_id))
            if self._games:
                self.get_source_list()

            self._retry = 0
            self._disconnected = False
            if status.get("status") == "Ok":
                title_id = status.get("running-app-titleid")
                name = status.get("running-app-name")

                if title_id and name is not None:
                    self._attr_state = MediaPlayerState.PLAYING

                    if self.media_content_id != title_id:
                        self._attr_media_content_id = title_id
                        if self._use_saved():
                            _LOGGER.debug("Using saved data for media: %s", title_id)
                            return

                        self._attr_media_title = name
                        self._attr_source = self._attr_media_title
                        self._attr_media_content_type = None
                        # Get data from PS Store.
                        self.hass.async_create_background_task(
                            self.async_get_title_data(title_id, name),
                            "ps4.media_player-get_title_data",
                        )
                elif self.state != MediaPlayerState.IDLE:
                    self.idle()
            elif self.state != MediaPlayerState.STANDBY:
                self.state_standby()

        elif self._retry > DEFAULT_RETRIES:
            self.state_unknown()
        else:
            self._retry += 1

    def _use_saved(self) -> bool:
        """Return True, Set media attrs if data is locked."""
        if self.media_content_id in self._games:
            store = cast(JsonObjectType, self._games[self.media_content_id])

            # If locked get attributes from file.
            if store.get(ATTR_LOCKED):
                self._attr_media_title = cast(str | None, store.get(ATTR_MEDIA_TITLE))
                self._attr_source = self._attr_media_title
                self._media_image = cast(str | None, store.get(ATTR_MEDIA_IMAGE_URL))
                self._attr_media_content_type = cast(
                    str | None, store.get(ATTR_MEDIA_CONTENT_TYPE)
                )
                return True
        return False

    def idle(self) -> None:
        """Set states for state idle."""
        self.reset_title()
        self._attr_state = MediaPlayerState.IDLE

    def state_standby(self) -> None:
        """Set states for state standby."""
        self.reset_title()
        self._attr_state = MediaPlayerState.STANDBY

    def state_unknown(self) -> None:
        """Set states for state unknown."""
        self.reset_title()
        self._attr_state = None
        if self._disconnected is False:
            _LOGGER.warning("PS4 could not be reached")
        self._disconnected = True
        self._retry = 0

    def reset_title(self) -> None:
        """Update if there is no title."""
        self._attr_media_title = None
        self._attr_media_content_id = None
        self._attr_media_content_type = None
        self._attr_source = None

    async def async_get_title_data(self, title_id: str, name: str) -> None:
        """Get PS Store Data."""

        app_name = None
        art = None
        media_type = None
        try:
            title = await self._ps4.async_get_ps_store_data(
                name, title_id, self._region
            )

        except PSDataIncomplete:
            title = None
        except asyncio.TimeoutError:
            title = None
            _LOGGER.error("PS Store Search Timed out")

        else:
            if title is not None:
                app_name = title.name
                art = title.cover_art
                # Assume media type is game if not app.
                if title.game_type != PS_TYPE_APP:
                    media_type = MediaType.GAME
                else:
                    media_type = MediaType.APP
            else:
                _LOGGER.error(
                    "Could not find data in region: %s for PS ID: %s",
                    self._region,
                    title_id,
                )

        finally:
            self._attr_media_title = app_name or name
            self._attr_source = self._attr_media_title
            self._media_image = art or None
            self._attr_media_content_type = media_type

            await self.hass.async_add_executor_job(self.update_list)
            self.async_write_ha_state()

    def update_list(self) -> None:
        """Update Game List, Correct data if different."""
        if self.media_content_id in self._games:
            store = cast(JsonObjectType, self._games[self.media_content_id])

            if (
                store.get(ATTR_MEDIA_TITLE) != self.media_title
                or store.get(ATTR_MEDIA_IMAGE_URL) != self._media_image
            ):
                self._games.pop(self.media_content_id)

        if self.media_content_id not in self._games:
            self.add_games(
                self.media_content_id,
                self._attr_media_title,
                self._media_image,
                self._attr_media_content_type,
            )
            self._games = load_games(self.hass, cast(str, self.unique_id))

        self.get_source_list()

    def get_source_list(self) -> None:
        """Parse data entry and update source list."""
        games = []
        for data in self._games.values():
            data = cast(JsonObjectType, data)
            games.append(cast(str, data[ATTR_MEDIA_TITLE]))
        self._attr_source_list = sorted(games)

    def add_games(
        self,
        title_id: str | None,
        app_name: str | None,
        image: str | None,
        g_type: str | None,
        is_locked: bool = False,
    ) -> None:
        """Add games to list."""
        games = self._games
        if title_id is not None and title_id not in games:
            game: JsonObjectType = {
                title_id: {
                    ATTR_MEDIA_TITLE: app_name,
                    ATTR_MEDIA_IMAGE_URL: image,
                    ATTR_MEDIA_CONTENT_TYPE: g_type,
                    ATTR_LOCKED: is_locked,
                }
            }
            games.update(game)
            save_games(self.hass, games, cast(str, self.unique_id))

    async def async_get_device_info(self, status: dict[str, Any] | None) -> None:
        """Set device info for registry."""
        # If cannot get status on startup, assume info from registry.
        if status is None:
            _LOGGER.info("Assuming status from registry")
            e_registry = er.async_get(self.hass)
            d_registry = dr.async_get(self.hass)
            for entity_id, entry in e_registry.entities.items():
                if entry.config_entry_id == self._entry_id:
                    self._attr_unique_id = entry.unique_id
                    self.entity_id = entity_id
                    break
            for device in d_registry.devices.values():
                if self._entry_id in device.config_entries:
                    self._attr_device_info = DeviceInfo(
                        identifiers=device.identifiers,
                        manufacturer=device.manufacturer,
                        model=device.model,
                        name=device.name,
                        sw_version=device.sw_version,
                    )
                    break

        else:
            _sw_version = status["system-version"]
            _sw_version = _sw_version[1:4]
            sw_version = f"{_sw_version[0]}.{_sw_version[1:]}"
            self._attr_device_info = DeviceInfo(
                identifiers={(PS4_DOMAIN, status["host-id"])},
                manufacturer="Sony Interactive Entertainment Inc.",
                model="PlayStation 4",
                name=status["host-name"],
                sw_version=sw_version,
            )

            self._attr_unique_id = format_unique_id(self._creds, status["host-id"])

    async def async_will_remove_from_hass(self) -> None:
        """Remove Entity from Home Assistant."""
        # Close TCP Transport.
        if self._ps4.connected:
            await self._ps4.close()
        self.unsubscribe_to_protocol()
        self.hass.data[PS4_DATA].devices.remove(self)

    @property
    def entity_picture(self) -> str | None:
        """Return picture."""
        if (
            self.state == MediaPlayerState.PLAYING
            and self.media_content_id is not None
            and (image_hash := self.media_image_hash) is not None
        ):
            return (
                f"/api/media_player_proxy/{self.entity_id}?"
                f"token={self.access_token}&cache={image_hash}"
            )
        return None

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if self.media_content_id is None:
            return None
        return self._media_image

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._ps4.standby()

    async def async_turn_on(self) -> None:
        """Turn on the media player."""
        self._ps4.wakeup()

    async def async_toggle(self) -> None:
        """Toggle media player."""
        await self._ps4.toggle()

    async def async_media_pause(self) -> None:
        """Send keypress ps to return to menu."""
        await self.async_send_remote_control("ps")

    async def async_media_stop(self) -> None:
        """Send keypress ps to return to menu."""
        await self.async_send_remote_control("ps")

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        for title_id, data in self._games.items():
            data = cast(JsonObjectType, data)
            game = cast(str, data[ATTR_MEDIA_TITLE])
            if (
                source.lower().encode(encoding="utf-8")
                == game.lower().encode(encoding="utf-8")
                or source == title_id
            ):
                _LOGGER.debug(
                    "Starting PS4 game %s (%s) using source %s", game, title_id, source
                )

                await self._ps4.start_title(title_id, self.media_content_id)
                return

        _LOGGER.warning("Could not start title. '%s' is not in source list", source)
        return

    async def async_send_command(self, command: str) -> None:
        """Send Button Command."""
        await self.async_send_remote_control(command)

    async def async_send_remote_control(self, command: str) -> None:
        """Send RC command."""
        await self._ps4.remote_control(command)
