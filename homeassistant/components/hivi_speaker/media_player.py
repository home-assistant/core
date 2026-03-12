import asyncio
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from xml.sax.saxutils import escape

import aiohttp
import xmltodict
from didl_lite import didl_lite
from mutagen import File

from homeassistant.components.dlna_dms.media_source import DmsMediaSource
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerState,
    MediaPlayerEntityFeature,
    MediaType,
    BrowseMedia,
    async_process_play_media_url,
)
from homeassistant.components.media_source import BrowseMediaSource, MediaSourceItem
from homeassistant.const import (
    STATE_IDLE,
    STATE_PLAYING,
    STATE_PAUSED,
    STATE_UNAVAILABLE,
)
from homeassistant.components import media_source
from homeassistant.components.dlna_dms.const import DOMAIN as DLNA_DMS_DOMAIN
from .device import HIVIDevice
from .device_manager import HIVIDeviceManager
from .const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up media_player platform"""
    device_manager: HIVIDeviceManager = hass.data[DOMAIN][config_entry.entry_id][
        "device_manager"
    ]
    device_manager.set_add_entities_callback("media_player", async_add_entities)

    # Initially add buttons for existing devices
    entities = []
    for device in device_manager.device_data_registry._device_data.values():
        if device.is_available_for_media:
            entity = HIVIMediaPlayerEntity(device, device_manager, hass)
            entities.append(entity)

    if entities:
        async_add_entities(entities, update_before_add=True)


class HIVIMediaPlayerEntityHub:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.media_players = {}

    def get_media_player(self, unique_id: str):
        return self.media_players.get(unique_id)

    def add_media_player(self, media_player):
        self.media_players[media_player.unique_id] = media_player


class HIVIMediaPlayerEntity(MediaPlayerEntity):
    """HIVI speaker media player entity"""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: HIVIMediaPlayerEntityHub,
        device_manager: HIVIDeviceManager,
        device: HIVIDevice,
    ):
        self._device = device
        self._device_manager = device_manager
        self.hass = hass
        self._hub = hub

        # Connection information
        self._base_url = None
        self._avtransport_url = None
        self._rendering_control_url = None
        self._session = None

        # Control update frequency and connection status
        self._last_update_time = 0
        self._update_interval = 30
        self._last_volume_update = 0
        self._volume_update_interval = 60
        self._last_mute_update = 0
        self._mute_update_interval = 60
        self._connection_ok = True  # Connection status tracking
        self._connection_fail_count = 0
        self._max_connection_fails = 3

        # Status
        self._attr_state = STATE_IDLE
        self._attr_volume_level = 0.5
        self._attr_is_volume_muted = False
        self._attr_media_title = None
        self._attr_media_artist = None
        self._attr_media_album_name = None
        self._media_duration = None
        self._media_position = None
        self._media_position_updated_at = None

        # Basic attributes
        self._attr_name = f"{device.friendly_name}_media_player"
        self._attr_unique_id = f"{device.unique_id}_media_player"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.speaker_device_id)},
            "name": device.friendly_name,
            "manufacturer": device.manufacturer,
            "model": device.model,
        }

        # Supported features
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.BROWSE_MEDIA
        )

        self._attr_media_image_url = None

        self._hub.add_media_player(self)

    async def async_added_to_hass(self):
        """Called when entity is added to Home Assistant"""
        # Create session but don't connect immediately
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

    async def async_will_remove_from_hass(self):
        """Called when removed from Home Assistant"""
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def state(self) -> MediaPlayerState:
        """Return playback status"""
        if not self.available:
            return STATE_UNAVAILABLE
        return self._attr_state

    @property
    def available(self) -> bool:
        """Whether device is available"""
        return (
            self._device.is_available_for_media
            and self._session is not None
            and self._connection_ok
        )

    async def _soap_request(
        self, url: str, service_type: str, action: str, **kwargs
    ) -> Optional[Dict]:
        """Send SOAP request (optimize connection stability)"""
        if not self._session or not url:
            _LOGGER.debug(f"SOAP request failed: no session or URL, url={url}")
            return None

        # Retry mechanism
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # HIVI speaker specific SOAP format
                args_xml = ""
                for key, value in kwargs.items():
                    args_xml += f"<{key}>{value}</{key}>"

                # Use correct namespace
                soap_envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body>
<u:{action} xmlns:u="{service_type}">
{args_xml}
</u:{action}>
</s:Body>
</s:Envelope>'''

                headers = {
                    "Content-Type": 'text/xml; charset="utf-8"',
                    "SOAPAction": f'"{service_type}#{action}"',
                    "User-Agent": "HomeAssistant/1.0",
                }

                _LOGGER.debug(
                    f"Sending SOAP request to {url} (attempt {attempt + 1}/{max_retries})"
                )

                # Use shorter timeout to avoid long blocking
                timeout = aiohttp.ClientTimeout(total=8, connect=3, sock_read=5)

                # Create new temporary session for each request to avoid connection pool issues
                async with aiohttp.ClientSession(timeout=timeout) as temp_session:
                    async with temp_session.post(
                        url, data=soap_envelope.encode("utf-8"), headers=headers
                    ) as response:
                        response_text = await response.text()
                        _LOGGER.debug(f"SOAP response status: {response.status}")

                        if response.status == 200:
                            # Connection successful, reset failure count
                            self._connection_ok = True
                            self._connection_fail_count = 0

                            try:
                                # Try to parse XML response
                                response_dict = xmltodict.parse(response_text)

                                # Find response section
                                envelope = response_dict.get("s:Envelope", {})
                                if not envelope:
                                    envelope = response_dict.get("Envelope", {})

                                body = envelope.get("s:Body", {})
                                if not body:
                                    body = envelope.get("Body", {})

                                # Find response
                                for key, value in body.items():
                                    if "Response" in key or action in key:
                                        return value

                                return body

                            except Exception as parse_error:
                                _LOGGER.debug(
                                    f"Failed to parse SOAP response: {parse_error}"
                                )
                                return {"raw_response": response_text}
                        else:
                            _LOGGER.warning(
                                f"SOAP request failed: HTTP {response.status}"
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(0.5 * (attempt + 1))
                                continue
                            return None

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _LOGGER.debug(
                    f"SOAP request network error (attempt {attempt + 1}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue

                # Record connection failure
                self._connection_fail_count += 1
                if self._connection_fail_count >= self._max_connection_fails:
                    self._connection_ok = False
                    _LOGGER.warning(
                        f"Too many device connection failures, marked as unavailable"
                    )

                return None

            except Exception as e:
                _LOGGER.error(f"SOAP request error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return None

        return None

    async def async_update(self):
        """Update device status (optimize connection stability)"""
        current_time = time.time()

        # Check if update is needed
        if current_time - self._last_update_time < self._update_interval:
            return

        # If connection is broken, reduce update frequency
        if not self._connection_ok:
            if current_time - self._last_update_time < 300:  # Try again after 5 minutes
                return
            else:
                _LOGGER.debug("Try to reconnect the device")
                self._connection_ok = True
                self._connection_fail_count = 0

        if not self.available or not self._device.ip_addr:
            return

        self._last_update_time = current_time

        try:
            # If URL not discovered, try to discover
            if not self._avtransport_url:
                await self._discover_services()

            if not self._avtransport_url:
                return

            # Get transport info (most important, update every time)
            result = await self._soap_request(
                self._avtransport_url,
                "urn:schemas-upnp-org:service:AVTransport:1",
                "GetTransportInfo",
                InstanceID="0",
            )

            if result:
                transport_state = result.get("CurrentTransportState", "")
                _LOGGER.debug(f"Transport status: {transport_state}")

                if transport_state == "PLAYING":
                    self._attr_state = STATE_PLAYING
                elif transport_state == "PAUSED_PLAYBACK":
                    self._attr_state = STATE_PAUSED
                elif transport_state in ["STOPPED", "NO_MEDIA_PRESENT"]:
                    self._attr_state = STATE_IDLE
                else:
                    self._attr_state = STATE_IDLE

            # Only get volume and mute info when connection is normal
            if self._connection_ok and self._rendering_control_url:
                # Get volume info (reduce frequency)
                if (
                    current_time - self._last_volume_update
                    >= self._volume_update_interval
                ):
                    self._last_volume_update = current_time

                    result = await self._soap_request(
                        self._rendering_control_url,
                        "urn:schemas-upnp-org:service:RenderingControl:1",
                        "GetVolume",
                        InstanceID="0",
                    )

                    if result and "CurrentVolume" in result:
                        volume = int(result["CurrentVolume"])
                        self._attr_volume_level = volume / 100.0
                        _LOGGER.debug(f"Volume: {volume}%")

                # Get mute info (reduce frequency)
                if current_time - self._last_mute_update >= self._mute_update_interval:
                    self._last_mute_update = current_time

                    result = await self._soap_request(
                        self._rendering_control_url,
                        "urn:schemas-upnp-org:service:RenderingControl:1",
                        "GetMute",
                        InstanceID="0",
                    )

                    if result and "CurrentMute" in result:
                        mute = result["CurrentMute"]
                        self._attr_is_volume_muted = str(mute) in [
                            "1",
                            "True",
                            "true",
                            "1",
                        ]
                        _LOGGER.debug(f"Mute status: {self._attr_is_volume_muted}")

        except Exception as e:
            _LOGGER.debug(f"Error updating device status: {e}")

    async def _discover_services(self):
        """Discover DLNA services (optimize error handling)"""
        try:
            if not self._device.ip_addr:
                return

            description_url = f"http://{self._device.ip_addr}:49152/description.xml"
            _LOGGER.debug(f"Discover services: {description_url}")

            # Use temporary session to discover services
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(description_url) as response:
                    if response.status == 200:
                        xml_data = await response.text()
                        self._base_url = f"http://{self._device.ip_addr}:49152"

                        # Parse XML
                        root = ET.fromstring(xml_data)

                        # Register namespace
                        ns = {"": "urn:schemas-upnp-org:device-1-0"}

                        # Find AVTransport service
                        for service in root.findall(".//service", ns):
                            service_type = service.find("serviceType", ns)
                            if (
                                service_type is not None
                                and "AVTransport" in service_type.text
                            ):
                                control_url = service.find("controlURL", ns)
                                if control_url is not None:
                                    # Ensure URL is complete
                                    control_path = control_url.text
                                    if control_path.startswith("/"):
                                        self._avtransport_url = f"http://{self._device.ip_addr}:49152{control_path}"
                                    else:
                                        self._avtransport_url = f"http://{self._device.ip_addr}:49152/{control_path}"
                                    _LOGGER.debug(
                                        f"Discover AVTransport URL: {self._avtransport_url}"
                                    )

                            if (
                                service_type is not None
                                and "RenderingControl" in service_type.text
                            ):
                                control_url = service.find("controlURL", ns)
                                if control_url is not None:
                                    control_path = control_url.text
                                    if control_path.startswith("/"):
                                        self._rendering_control_url = f"http://{self._device.ip_addr}:49152{control_path}"
                                    else:
                                        self._rendering_control_url = f"http://{self._device.ip_addr}:49152/{control_path}"
                                    _LOGGER.debug(
                                        f"Discover RenderingControl URL: {self._rendering_control_url}"
                                    )

        except Exception as e:
            _LOGGER.debug(f"Error discovering services: {e}")

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ):
        # _LOGGER.debug(f"$$$4 media_content_id = {media_content_id}")
        """Return browsable media directory structure"""

        # Parse media_content_id
        if media_content_id:
            # Separate path part (media-source://domain/path → path)
            path_parts = (
                media_content_id.split("/")[3:]
                if media_content_id.startswith("media-source://")
                else []
            )
            clean_path = "/".join(path_parts) if path_parts else media_content_id
        else:
            clean_path = ""

        # _LOGGER.debug(f"$$$4 clean_path = {clean_path}")

        if media_content_id is None:
            # Root directory: Add entries for different media sources
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="root",
                media_content_type="directory",
                media_class="directory",
                title="Media source list",
                can_play=False,
                can_expand=True,
                children=[
                    # Local files entry
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier="local",  # Use identifier to distinguish media sources
                        media_content_type="directory",
                        media_class="directory",
                        title="Local files",
                        can_play=False,
                        can_expand=True,
                        thumbnail="https://brands.home-assistant.io/_/media_source/icon.png",
                    ),
                    # DLNA device entry
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier="dlna",
                        media_content_type="directory",
                        media_class="directory",
                        title="DLNA devices",
                        can_play=False,
                        can_expand=True,
                        thumbnail="https://brands.home-assistant.io/_/dlna_dms/icon.png",
                    ),
                ],
            )
        else:
            if media_content_id.startswith("media-source://"):
                domain, _, identifier = media_content_id[
                    len("media-source://") :
                ].partition("/")
                if domain == DLNA_DMS_DOMAIN:
                    return await self._browse_dlna_dms(identifier)
                # elif domain == DOMAIN:
                #     media_content_id = identifier
                # else:
                #     return await media_source.async_browse_media(
                #         self.hass, media_content_id
                #     )
                # Determine browsing path based on media_content_id
                elif identifier.endswith("local"):
                    # _LOGGER.debug("1111")
                    # Load root directory of local files
                    return await self._browse_local_media(root=True)
                elif identifier.startswith("local/"):
                    # _LOGGER.debug(f"2222 clean_path = {clean_path}")
                    # Load subdirectory of local files (e.g., "local/Music")
                    subpath = identifier.split("local/")[1]
                    return await self._browse_local_media(subpath=subpath)
                elif identifier == "dlna":
                    # Load DLNA device list
                    return await self._browse_dlna_dms(None)
                elif identifier.startswith("dlna/"):
                    # Load content of a DLNA device
                    device_id = identifier.split("dlna/")[1]
                    return await self._browse_dlna_content(device_id)
                    # Parse media_content_id (compatible with media-source:// format)

                else:
                    # Other paths (e.g., playlists)
                    return await self._fetch_media_items(identifier)
            else:
                pass

    async def _browse_local_media(self, root=False, subpath=None):
        """Browse local file system"""
        base_path = "/media"  # Local media root directory
        if root:
            current_path = base_path
        else:
            current_path = os.path.join(base_path, subpath)

        def _scan_dir(path):
            with os.scandir(path) as it:
                return list(it)

        entries = await asyncio.to_thread(_scan_dir, current_path)

        children = []
        for entry in entries:
            # _LOGGER.debug(f"entry = {entry}")
            if entry.is_dir():
                rel_path = os.path.relpath(entry.path, base_path)
                _LOGGER.debug(f"subpath = {rel_path}")
                # Subdirectory
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"local/{rel_path}",
                        media_content_type="directory",
                        media_class="directory",
                        title=entry.name,
                        can_play=False,
                        can_expand=True,
                    )
                )
            elif entry.is_file() and entry.name.endswith(
                (".mp3", ".flac", ".wav", ".m3u8")
            ):
                # _LOGGER.debug(f"subpath = {subpath}")
                # _LOGGER.debug(f"entry.name = {entry.name}")

                # # Audio file - generate HTTP link
                # # media_id = (
                # #     f"media-source://{DOMAIN}/local/{subpath}/{entry.name}"
                # #     if subpath
                # #     else f"media-source://{DOMAIN}/local/{entry.name}"
                # # )
                # media_id = (
                #     f"media-source://media_source/local/{subpath}/{entry.name}"
                #     if subpath
                #     else f"media-source://media_source/local/{entry.name}"
                # )

                # # _LOGGER.debug(f"media_id 1 = {media_id}")

                # # Parse HTTP link
                # try:
                #     if media_source.is_media_source_id(media_id):
                #         sourced_media = await media_source.async_resolve_media(
                #             self.hass, media_id, self.entity_id
                #         )
                #         # _LOGGER.debug(f"sourced_media = {sourced_media}")
                #         media_type = sourced_media.mime_type
                #         media_id = sourced_media.url
                #         _LOGGER.debug("sourced_media is %s", sourced_media)
                #         if sourced_metadata := getattr(
                #             sourced_media, "didl_metadata", None
                #         ):
                #             # didl_metadata = didl_lite.to_xml_string(
                #             #     sourced_metadata
                #             # ).decode("utf-8")
                #             title = sourced_metadata.title

                #     # If media ID is a relative URL, we serve it from HA.
                #     media_id = async_process_play_media_url(self.hass, media_id)
                #     # _LOGGER.debug(f"media_id = {media_id}")

                #     http_url = media_id

                # except Exception as e:
                #     _LOGGER.error(f"resolved error, e = {str(e)}")
                #     http_url = None  # If parsing fails, return None or default path

                # _LOGGER.debug(f"http_url = {http_url}")

                if subpath is None:
                    identifier = f"local_file/{entry.name}"
                else:
                    identifier = f"local_file/{subpath}/{entry.name}"

                # Audio file
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=identifier,
                        media_content_type="music",
                        media_class="music",
                        title=entry.name,
                        can_play=True,
                        can_expand=False,
                        # file_path=os.path.join(current_path, entry.name),
                        # http_url=http_url,  # Add HTTP access URL
                    )
                )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="local" if root else f"local/{subpath}",
            media_content_type="directory",
            media_class="directory",
            title="Local files" if root else os.path.basename(subpath),
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _fetch_media_items(self, media_content_id: str):
        """Load specific media content based on media_content_id"""
        # 1. Handle "playlists" subdirectory (corresponds to "Playlist" item in root directory)
        if media_content_id == "playlists":
            # Example: Return specific items in playlist
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="playlists",
                media_content_type="directory",
                media_class="directory",
                title="Playlists",
                can_play=False,
                can_expand=True,
                children=[
                    # Assume there are two items in playlist
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier="playlist_1",
                        media_content_type="music",
                        media_class="playlist_item",
                        title="My playlist 1",
                        can_play=True,  # Playable
                        can_expand=False,
                    ),
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier="playlist_2",
                        media_content_type="music",
                        media_class="playlist_item",
                        title="My playlist 2",
                        can_play=True,
                        can_expand=False,
                    ),
                ],
            )

        # 2. Handle other media_content_id (extend based on your actual needs)
        elif media_content_id.startswith("local/"):
            # Local file subdirectory (refer to previous local file browsing logic)
            return await self._browse_local_media(
                subpath=media_content_id.split("local/")[1]
            )

        elif media_content_id.startswith("dlna/"):
            # DLNA device content (refer to previous DLNA browsing logic)
            device_id = media_content_id.split("dlna/")[1]
            return await self._browse_dlna_content(device_id)

        # 3. Handle unknown media_content_id
        else:
            # Return empty directory or error message
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=media_content_id,
                media_content_type="directory",
                media_class="directory",
                title="Unknown directory",
                can_play=False,
                can_expand=False,
                children=[],  # Empty directory
            )

    async def _browse_dlna_dms(self, path: str) -> BrowseMedia:
        """Browse DLNA DMS content"""
        try:
            # Use media_source component to browse DLNA content
            media_id = None
            if path is None:
                media_id = "media-source://dlna_dms"
            else:
                media_id = f"media-source://{DLNA_DMS_DOMAIN}/{path}"
            result = await media_source.async_browse_media(
                hass=self.hass, media_content_id=media_id
            )

            # Convert result to new format
            if result.children:
                new_children = []
                for child in result.children:
                    # Create new media item with all necessary parameters
                    new_child = BrowseMedia(
                        media_content_id=child.media_content_id,
                        media_content_type=child.media_content_type,
                        media_class=child.media_class,
                        title=child.title,
                        can_play=child.can_play,
                        can_expand=child.can_expand,
                    )

                    # Optional attributes need to be checked for existence
                    if hasattr(child, "thumbnail"):
                        new_child.thumbnail = child.thumbnail

                    new_children.append(new_child)

                result = BrowseMedia(
                    media_content_id=result.media_content_id,
                    media_content_type=result.media_content_type,
                    media_class=result.media_class,
                    title=result.title,
                    can_play=result.can_play,
                    can_expand=result.can_expand,
                    children=new_children,
                )

                # Optional attributes need to be checked for existence
                if hasattr(result, "thumbnail"):
                    result.thumbnail = result.thumbnail

            return result
        except Exception as e:
            _LOGGER.error("Failed to browse DLNA DMS content: %s", str(e))
            # raise BrowseError("Cannot browse DLNA media server content") from e

    async def _get_dlna_media_url(self, media_id: str) -> str | None:
        """Parse DLNA DMS media file URL (2025.9+ final revision)"""
        try:
            # 1. Validate and parse media_id
            if not media_id.startswith("media-source://dlna_dms/"):
                _LOGGER.error("Invalid DLNA media ID format: %s", media_id)
                return None

            # 2. Extract server ID and object ID (handle Windows paths)
            path = media_id[len("media-source://dlna_dms/") :].replace("\\", "/")
            server_id, _, object_id = path.partition("/")

            if not server_id or not object_id:
                _LOGGER.error("Malformed DLNA media ID: %s", media_id)
                return None

            # 3. Create media item (2025.9+ latest parameter requirements)
            media_item = MediaSourceItem(
                hass=self.hass,  # Must pass Home Assistant instance
                domain="dlna_dms",  # Must specify domain
                identifier=f"{server_id}/{object_id}",  # Media identifier
                target_media_player=self.entity_id,  # Must specify target player
            )

            # 4. Parse media URL
            dms_source = DmsMediaSource(self.hass)
            resolved_media = await dms_source.async_resolve_media(media_item)

            if not resolved_media or not resolved_media.url:
                _LOGGER.error("Failed to resolve DLNA media: %s", media_id)
                return None

            # 5. Process URL
            media_url = async_process_play_media_url(self.hass, resolved_media.url)
            _LOGGER.debug("Resolved DLNA URL: %s", media_url)
            return media_url

        except Exception as e:
            _LOGGER.error("DLNA URL resolution failed: %s", str(e), exc_info=True)
            return None

    # media_id
    # When playing locally
    # media-source://ss-mcs1000/local_file/daoxiang.mp3
    # When playing DMS
    # media-source://dlna_dms/mediamonkey_library_chenji_pc/:0\\Music\\All files\\ItemID=4.mp3
    async def _convert_media_id_to_url_and_meta(self, media_id):
        """Convert a media ID to a playable URL and metadata."""
        http_url = None
        meta = None

        if media_id.startswith("media-source://dlna_dms/"):
            # Handle DLNA media
            http_url, meta = await self._handle_dlna_media(media_id)
        else:
            # Handle local media
            http_url, meta = await self._handle_local_media(media_id)

        _LOGGER.debug(f"http_url = {http_url}")
        return http_url, meta

    async def _handle_dlna_media(self, media_id):
        """Process DLNA media source and extract metadata."""
        try:
            if media_source.is_media_source_id(media_id):
                sourced_media = await media_source.async_resolve_media(
                    self.hass, media_id, self.entity_id
                )
                _LOGGER.debug(f"sourced_media = {sourced_media}")

                # Extract metadata if available
                meta = self._extract_dlna_metadata(sourced_media)

                # Get the media URL
                media_url = await self._get_dlna_media_url(media_id)
                if not media_url:
                    _LOGGER.error("Cannot resolve DLNA media URL")
                    return None, None

                return media_url, meta

        except Exception as e:
            _LOGGER.error(f"resolved error, e = {str(e)}")
            return None, None

    def _extract_dlna_metadata(self, sourced_media):
        """Extract metadata from DLNA media."""
        if sourced_metadata := getattr(sourced_media, "didl_metadata", None):
            didl_metadata = didl_lite.to_xml_string(sourced_metadata).decode("utf-8")
            title = (
                sourced_metadata.title
                if hasattr(sourced_metadata, "title")
                else "Unknown title"
            )
            artist = (
                sourced_metadata.artist
                if hasattr(sourced_metadata, "artist")
                else "Unknown artist"
            )
            album_art_uri = (
                sourced_metadata.album_art_uri
                if hasattr(sourced_metadata, "album_art_uri")
                else None
            )

            return {
                "title": title,
                "artist": artist,
                "album_art_uri": album_art_uri,
            }
        return None

    async def _handle_local_media(self, media_id):
        """Process local media file and extract metadata."""
        domain, identifier = parse_media_source_id(media_id)

        if not identifier.startswith("local_file/"):
            return None, None

        filename = identifier.split("local_file/")[1]
        _LOGGER.debug(f"async_play_media identifier = {identifier}")

        # Get metadata from MP3 file
        meta = await self.hass.async_add_executor_job(
            get_mp3_metadata, f"/media/{filename}"
        )

        # Resolve media URL
        media_id_2 = f"media-source://media_source/local/{filename}"
        _LOGGER.debug(f"async_play_media media_id_2 = {media_id_2}")

        try:
            if media_source.is_media_source_id(media_id_2):
                sourced_media = await media_source.async_resolve_media(
                    self.hass, media_id_2, self.entity_id
                )
                _LOGGER.debug(f"sourced_media = {sourced_media}")
                media_id_2 = sourced_media.url

            # Process media URL
            media_id_2 = async_process_play_media_url(self.hass, media_id_2)
            return media_id_2, meta

        except Exception as e:
            _LOGGER.error(f"resolved error, e = {str(e)}")
            return None, None

    async def async_play_media(self, media_type: str, media_id: str, **kwargs):
        """Play media (improved: parse media-source and validate URL)"""
        if not self._device.ip_addr:
            _LOGGER.error("Device IP address unavailable")
            return

        # Get album art and title from media_id if possible start
        http_url = None
        meta = None

        http_url, meta = await self._convert_media_id_to_url_and_meta(media_id)

        if http_url is not None:
            media_desc = {}
            if meta:
                media_desc = {
                    "url": http_url,
                    "title": meta.get("title"),
                    "artist": meta.get("artist"),
                    "album_art_uri": meta.get("album_art_uri"),
                }
                self._attr_media_title = meta.get("title")
                self._attr_media_artist = meta.get("artist")
                self._attr_media_image_url = meta.get("album_art_uri")
            else:
                media_desc = {
                    "url": http_url,
                }
                self._attr_media_image_url = None

        # Get album art and title from media_id if possible complete

        # First parse Home Assistant's media-source scheme
        media_url = media_id
        if media_id.startswith("media-source://"):
            try:
                _LOGGER.debug("Try to parse media-source: %s", media_id)
                resolved = await media_source.async_resolve_media(self.hass, media_id)
                media_url = resolved.url
                _LOGGER.debug("media-source url: %s", media_url)
            except Exception:
                _LOGGER.exception("Cannot parse media-source URL")
                # Return directly or continue with fallback solution
                return

        # Confirm it's an accessible http/https URL
        parsed = urlparse(media_url)
        if parsed.scheme not in ("http", "https"):
            _LOGGER.error(
                "Media URL is not HTTP/HTTPS, cannot play directly: %s", media_url
            )
            return

        # Infer mime type (can be extended as needed)
        path = parsed.path.lower()
        mime_type = "audio/mpeg"
        if path.endswith(".wav"):
            mime_type = "audio/wav"
        elif path.endswith(".flac"):
            mime_type = "audio/flac"
        elif path.endswith(".aac") or path.endswith(".m4a") or path.endswith(".mp4"):
            mime_type = "audio/mp4"

        # Metadata (from kwargs or default)
        title = kwargs.get("metadata", {}).get("title", "Unknown audio")
        artist = kwargs.get("metadata", {}).get("artist", "Unknown artist")
        album = kwargs.get("metadata", {}).get("album", "")

        title_escaped = escape(title)
        artist_escaped = escape(artist)
        album_escaped = escape(album)

        didl_template = """<?xml version="1.0" encoding="utf-8"?>
        <DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
                xmlns:dc="http://purl.org/dc/elements/1.1/"
                xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
            <item id="1" parentID="0" restricted="0">
                <dc:title>{title}</dc:title>
                <dc:creator>{artist}</dc:creator>
                <upnp:artist>{artist}</upnp:artist>
                <upnp:album>{album}</upnp:album>
                <upnp:class>object.item.audioItem.musicTrack</upnp:class>
                <res protocolInfo="http-get:*:{mime_type}:*">{media_url}</res>
            </item>
        </DIDL-Lite>"""

        simple_metadata = didl_template.format(
            title=title_escaped,
            artist=artist_escaped,
            album=album_escaped,
            mime_type=mime_type,
            media_url=media_url,
        )

        _LOGGER.debug("Prepare to send SetAVTransportURI to %s", self._avtransport_url)
        _LOGGER.debug("CurrentURI: %s", media_url)
        _LOGGER.debug("CurrentURIMetaData (short preview): %s", simple_metadata[:200])

        # If control URL looks wrong, print and warn
        if (
            not self._avtransport_url
            or "AVTransport" not in self._avtransport_url
            and "transport" not in self._avtransport_url
        ):
            _LOGGER.debug("AVTransport control URL: %s", self._avtransport_url)
            # Optional: rediscover services self._discover_services()

        # First try without metadata (some devices prefer empty metadata)
        result = await self._soap_request(
            self._avtransport_url,
            "urn:schemas-upnp-org:service:AVTransport:1",
            "SetAVTransportURI",
            InstanceID="0",
            CurrentURI=media_url,
            CurrentURIMetaData="",
        )

        if result is None:
            _LOGGER.debug("Empty metadata method failed, try with DIDL-Lite method")
            result = await self._soap_request(
                self._avtransport_url,
                "urn:schemas-upnp-org:service:AVTransport:1",
                "SetAVTransportURI",
                InstanceID="0",
                CurrentURI=media_url,
                CurrentURIMetaData=simple_metadata,
            )

        if result is None:
            _LOGGER.error("SetAVTransportURI final failure (device returned 400)")
            # Enable more detailed debugging: print HTTP response body/request body (supported by your _soap_request)
            return

        # Wait and send Play (same as your original logic)
        await asyncio.sleep(2)
        play_result = await self._soap_request(
            self._avtransport_url,
            "urn:schemas-upnp-org:service:AVTransport:1",
            "Play",
            InstanceID="0",
            Speed="1",
        )

        if play_result is not None:
            self._attr_state = STATE_PLAYING
            self.async_write_ha_state()
            _LOGGER.debug("Start playing media")
            await asyncio.sleep(1)
            await self.async_update()
            return

        _LOGGER.warning("Play command failed (Play returned empty).")

    # Other methods remain unchanged...
    async def async_media_play(self):
        """Play"""
        _LOGGER.debug("Execute play command")

        if not self.available or not self._avtransport_url:
            return

        try:
            result = await self._soap_request(
                self._avtransport_url,
                "urn:schemas-upnp-org:service:AVTransport:1",
                "Play",
                InstanceID="0",
                Speed="1",
            )

            if result is not None:
                self._attr_state = STATE_PLAYING
                self.async_write_ha_state()
                _LOGGER.debug("Send play command")

        except Exception as e:
            _LOGGER.error(f"Error when sending play command: {e}")

    async def async_media_pause(self):
        """Pause"""
        if not self.available or not self._avtransport_url:
            return

        try:
            result = await self._soap_request(
                self._avtransport_url,
                "urn:schemas-upnp-org:service:AVTransport:1",
                "Pause",
                InstanceID="0",
            )

            if result is not None:
                self._attr_state = STATE_PAUSED
                self.async_write_ha_state()
                _LOGGER.debug("Send pause command")

        except Exception as e:
            _LOGGER.error(f"Error when sending pause command: {e}")

    async def async_media_stop(self):
        """Stop"""
        if not self.available or not self._avtransport_url:
            return

        try:
            result = await self._soap_request(
                self._avtransport_url,
                "urn:schemas-upnp-org:service:AVTransport:1",
                "Stop",
                InstanceID="0",
            )

            if result is not None:
                self._attr_state = STATE_IDLE
                self.async_write_ha_state()
                _LOGGER.debug("Send stop command")

        except Exception as e:
            _LOGGER.error(f"Error when sending stop command: {e}")

    async def async_set_volume_level(self, volume: float):
        """Set volume"""
        if not self.available or not self._rendering_control_url:
            return

        try:
            volume_int = int(volume * 100)
            result = await self._soap_request(
                self._rendering_control_url,
                "urn:schemas-upnp-org:service:RenderingControl:1",
                "SetVolume",
                InstanceID="0",
                DesiredVolume=str(volume_int),
            )

            if result is not None:
                self._attr_volume_level = volume
                self.async_write_ha_state()
                _LOGGER.debug(f"Set volume: {volume_int}%")

        except Exception as e:
            _LOGGER.error(f"Error when setting volume: {e}")

    async def async_mute_volume(self, mute: bool):
        """Mute"""
        if not self.available or not self._rendering_control_url:
            return

        try:
            result = await self._soap_request(
                self._rendering_control_url,
                "urn:schemas-upnp-org:service:RenderingControl:1",
                "SetMute",
                InstanceID="0",
                DesiredMute="1" if mute else "0",
            )

            if result is not None:
                self._attr_is_volume_muted = mute
                self.async_write_ha_state()
                _LOGGER.debug(f"Set mute: {mute}")

        except Exception as e:
            _LOGGER.error(f"Error when setting mute: {e}")

    @property
    def extra_state_attributes(self):
        """Extra attributes"""
        attrs = {
            "speaker_device_id": self._device.speaker_device_id,
            "ip_addr": self._device.ip_addr,
            "slave_count": self._device.slave_device_num,
            "sync_group_status": getattr(
                self._device.sync_group_status,
                "value",
                str(self._device.sync_group_status),
            ),
            "dlna_available": self._avtransport_url is not None,
            "connection_ok": self._connection_ok,
            "connection_fail_count": self._connection_fail_count,
        }

        if self._avtransport_url:
            attrs["avtransport_url"] = self._avtransport_url

        if self._rendering_control_url:
            attrs["rendering_control_url"] = self._rendering_control_url

        return attrs


def parse_media_source_id(media_id: str) -> tuple[str, str]:
    """Parse media-source:// URI (compatibility implementation)"""
    if not media_id.startswith("media-source://"):
        raise ValueError(f"Invalid media source ID: {media_id}")

    parts = media_id.split("/")
    if len(parts) < 4:
        raise ValueError(f"Invalid media source ID format: {media_id}")

    domain = parts[2]
    identifier = "/".join(parts[3:])
    return domain, identifier



def decode_id3_text(text):
    """Try to fix Chinese garbled text"""
    if not text or not isinstance(text, str):
        return text

    # Common encoding attempt order
    encodings = ["utf-8", "gbk", "big5", "latin1"]
    for enc in encodings:
        try:
            if isinstance(text, bytes):
                return text.decode(enc)
            return text.encode("latin1").decode(enc)
        except UnicodeError:
            continue
    return text  # If all fail, return original text


def get_mp3_metadata(file_path):
    try:
        audio = File(file_path)
        if audio is None:
            return None

        metadata = {
            "title": decode_id3_text(audio.get("title", [""])[0]),
            "artist": decode_id3_text(audio.get("artist", [""])[0]),
            "album": decode_id3_text(audio.get("album", [""])[0]),
            "duration": int(audio.info.length) if hasattr(audio, "info") else 0,
        }

        if hasattr(audio, "tags") and audio.tags:
            id3 = audio.tags
            metadata.update(
                {
                    "title": decode_id3_text(id3.get("TIT2", [""])[0]),
                    "artist": decode_id3_text(id3.get("TPE1", [""])[0]),
                    "album": decode_id3_text(id3.get("TALB", [""])[0]),
                }
            )

        return {k: v for k, v in metadata.items() if v}

    except Exception as e:
        _LOGGER.debug("Failed to extract metadata: %s", e)
        return None
