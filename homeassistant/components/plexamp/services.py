"""Handles communication with Plexamp services."""

import logging

import aiohttp
import defusedxml.ElementTree as ET

from homeassistant.components.media_player import MediaPlayerState, MediaType

from .const import NUMBER_TO_REPEAT_MODE
from .models import BaseMediaPlayerFactory
from .utils import replace_ip_prefix

_LOGGER = logging.getLogger(__name__)


class PlexampService:
    def __init__(
        self,
        plexamp_entity: BaseMediaPlayerFactory,
        plex_token: str | None,
    ) -> None:
        self._plex_token = plex_token
        self._plexamp_entity = plexamp_entity

        self._plex_identifier = plexamp_entity.client_identifier
        self._plex_ip_address = plexamp_entity.uri
        self._host = plexamp_entity.address
        self._device_name = plexamp_entity.name
        self._command_id = 1
        self.headers = {
            "X-Plex-Token": plex_token,
            "X-Plex-Target-Client-Identifier": plexamp_entity.client_identifier,
            "X-Plex-Client-Identifier": "Plex_HomeAssistant",
            "Accept": "application/json",
            "X-Plex-Product": "Plex_HomeAssistant",
            "X-Plex-Version": "4.9.3",
        }

        _LOGGER.debug("Starting PlexampService for: %s", plexamp_entity.name)

    async def send_playback_command(self, action: str) -> None:
        """Send a command to the player."""
        url = f"{self._plexamp_entity.uri}/player/playback/{action}"
        _LOGGER.debug("Sending playback command to %s: %s", self._device_name, url)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=10,
                ) as response:
                    response.raise_for_status()
            except aiohttp.ClientError as e:
                _LOGGER.error(
                    "Failed to send command %s in %s: %s",
                    action,
                    self._device_name,
                    e,
                )

    async def send_set_parameter_command(self, parameters: str) -> None:
        """Send a parameter command to the player."""
        url = f"{self._plexamp_entity.uri}/player/playback/setParameters?{parameters}"
        _LOGGER.debug("Sending parameter command to %s: %s", self._device_name, url)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=10,
                ) as response:
                    response.raise_for_status()
            except aiohttp.ClientError as e:
                _LOGGER.error(
                    "Failed to set parameter %s in %s: %s",
                    parameters,
                    self._device_name,
                    e,
                )

    async def play_media(self, media_type: MediaType | str, rating_key: str) -> None:
        if media_type == MediaType.PLAYLIST:
            await self._play_playlist(rating_key=rating_key)

    async def poll_device(self, poll_wait=0) -> dict:
        """Get device information from Plexamp.

        Returns:
            Dict[str, Union[str, bool, float, None]]: A dictionary containing the following keys:
                - 'state' (str): The state of the media player.
                - 'shuffle' (bool): Whether shuffle mode is enabled.
                - 'volume_level' (float): The current volume level.
                - 'volume_step' (float): The step size for volume adjustments.
                - 'repeat' (str or None): The repeat mode.
                - 'thumb' (str or None): The URL of the thumbnail image.
                - 'title' (str or None): The title of the currently playing media.
                - 'parent_title' (str or None): The title of the parent media.
                - 'grandparent_title' (str or None): The title of the grandparent media.
                - 'duration' (str or None): Duration in seconds of current playing media.
                - 'time' (str or None): Current position in seconds of playing media.
                - 'machineIdentifier' (str or None): Identifier of the device in Plex.
                - 'protocol' (str or None): http or https.
                - 'port' (str or None): by default, 32400.

        """

        base_url = f"{self._plexamp_entity.uri}/player/timeline/poll"
        url = f"{base_url}?wait={poll_wait}&includeMetadata=1&commandID={self._command_id}&type=music"
        _LOGGER.debug("Updating device: %s", self._device_name)

        device_information = {
            "state": MediaPlayerState.IDLE,
            "shuffle": False,
            "volume_level": 1.0,
            "volume_step": 0.1,
            "repeat": NUMBER_TO_REPEAT_MODE.get("0"),
            "thumb": "",
            "title": "",
            "parent_title": "",
            "duration": "",
            "time": "",
            "machineIdentifier": "",
            "protocol": "",
            "port": "32400",
        }
        _LOGGER.debug(
            "device: %s | url: %s | headers: %s", self._device_name, url, self.headers
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=10,
                ) as response:
                    _LOGGER.debug(
                        "device: %s | url: %s | response: %s",
                        self._device_name,
                        url,
                        response,
                    )
                    response.raise_for_status()
                    self._command_id += 1
                    content = await response.text()
                    root = ET.fromstring(content)

                    for timeline in root.findall("Timeline"):
                        if timeline.get("itemType") == "music":
                            return await self._async_get_playlist_tracks(
                                session=session,
                                device_information=device_information,
                                timeline=timeline,
                            )
                        # plexamp does not support photo and video, returned by Plex
                        break
                return device_information
        except (TimeoutError, aiohttp.ClientError) as e:
            _LOGGER.error("Error updating device %s, error: %s", self._device_name, e)
            return device_information

    async def _get_play_token(self) -> str | None:
        url = f"{self._plexamp_entity.server.get("uri")}/security/token?type=delegation&scope=all&includeFields=thumbBlurHash"
        async with aiohttp.ClientSession() as session:
            response = await session.get(url, headers=self.headers, timeout=10)
            if response.status == 200:
                data = await response.json()
                return data.get("MediaContainer", {}).get("token") or None
        return None

    async def _play_playlist(self, rating_key: str, shuffle=0):
        token = await self._get_play_token()
        if not token or not self._plexamp_entity.server.get("uri"):
            return

        base_url = f"{self._plexamp_entity.uri}/player/playback/createPlayQueue"
        server_identifier = self._plexamp_entity.server.get("identifier")
        uri = f"uri=server://{server_identifier}/com.plexapp.plugins.library/playlists/{rating_key}/items"
        token = f"token={token}"
        command_id = f"commandID={self._command_id + 1}"
        extra_parameters = (
            f"shuffle={shuffle}&includeExternalMedia=1&type=audio&includeFields=thumbBlurHash&linkToParent=true&linkToGrandparent=true"
        )

        url = f"{base_url}?{uri}&{token}&{command_id}&{extra_parameters}"
        _LOGGER.debug("Starting new playlist in %s with url %s", self._device_name, url)
        async with aiohttp.ClientSession() as session:
            await session.get(url, headers=self.headers, timeout=10)

    async def get_playlists(self) -> list[dict]:
        server_uri = self._plexamp_entity.server.get("uri")
        if not server_uri:
            return []
        base_url = f"{server_uri}/playlists/all"
        exclude_fields = "summary"
        exclude_elements = "Media,Director,Country"
        include_fields = "thumbBlurHash"
        parameters = f"type=15&playlistType=audio&excludeFields={exclude_fields}&excludeElements={exclude_elements}&includeFields={include_fields}"
        url = f"{base_url}?{parameters}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        playlists = await response.json()
                        playlist_mapped = []
                        for playlist in (
                            playlists.get("MediaContainer", {}).get("Metadata") or []
                        ):
                            playlist_mapped.append(
                                {
                                    "title": playlist.get("title"),
                                    "composite": playlist.get("composite"),
                                    "ratingKey": playlist.get("ratingKey"),
                                }
                            )

                        return playlist_mapped

            return []

        except aiohttp.ClientError | aiohttp.ServerTimeoutError as e:
            _LOGGER.error(
                "Error retrieving playlists for %s, error: %s", self._device_name, e
            )
            return []

    async def _async_get_playlist_tracks(
        self, session: aiohttp.ClientSession, device_information: dict, timeline: dict
    ):
        """
        Retrieve playlist tracks information.

        This method retrieves information about the tracks in the playlist currently being played on the Plexamp device.

        Parameters:
        - session: aiohttp.ClientSession: An aiohttp session for making HTTP requests.
        - device_information: dict: A dictionary containing device information to be updated.
        - timeline: dict: A dictionary containing timeline information retrieved from the Plexamp device.

        Returns:
        - dict: Updated device information dictionary.
        """

        status = timeline.get("state", MediaPlayerState.IDLE)
        _LOGGER.debug("device: %s has status %s", self._device_name, status)

        device_information["state"] = {
            "playing": MediaPlayerState.PLAYING,
            "paused": MediaPlayerState.PAUSED,
        }.get(status)

        device_information["shuffle"] = timeline.get("shuffle", 0) != "0"
        device_information["volume"] = float(timeline.get("volume", 1.0)) / 100

        device_information["duration"] = timeline.get("duration")
        device_information["time"] = timeline.get("time")
        device_information["machineIdentifier"] = timeline.get("machineIdentifier")
        device_information["protocol"] = timeline.get("protocol")
        device_information["port"] = timeline.get("port")

        repeat_mode_value = timeline.get("repeat", 0)
        device_information["repeat"] = NUMBER_TO_REPEAT_MODE.get(repeat_mode_value)

        # If the user didn't provide the token, we can't get queue info and metadata
        if not self._plex_token or not self._plex_ip_address:
            _LOGGER.debug(
                "device: %s - NO _plex_token or _plex_ip_address",
                self._device_name,
            )
            return device_information

        play_queue = timeline.get("containerKey")

        if not play_queue or not self._plexamp_entity.server.get("uri"):
            return device_information

        return await self._async_get_queue_data(session=session, device_information=device_information, play_queue=play_queue)

    async def _async_get_queue_data(
        self,
        session: aiohttp.ClientSession,
        device_information: dict,
        play_queue: str,
    ):
        """
        Retrieve queue data for the currently playing playlist.

        This method retrieves information about the tracks in the playlist currently being played on the Plex device.

        Parameters:
        - session: aiohttp.ClientSession: An aiohttp session for making HTTP requests.
        - device_information: dict: A dictionary containing device information to be updated.
        - play_queue: str: URL of the Plex play queue.

        Returns:
        - dict: Updated device information dictionary.

        """
        play_queue_url = f"{self._plexamp_entity.server.get("uri")}{play_queue}"
        _LOGGER.debug("playing queue: %s", play_queue_url)

        try:
            async with session.get(
                play_queue_url, timeout=10, headers=self.headers
            ) as queue_data:
                queue = await queue_data.json() if queue_data.status == 200 else None
                if not queue:
                    return device_information

                currently_playing_id = queue.get("MediaContainer", {}).get(
                    "playQueueSelectedItemID"
                )

                if currently_playing_id is not None:
                    metadata = queue.get("MediaContainer", {}).get("Metadata", [])
                    currently_playing_metadata = next(
                        (
                            item
                            for item in metadata
                            if item.get("playQueueItemID") == currently_playing_id
                        ),
                        None,
                    )

                    thumb_url = currently_playing_metadata.get("thumb")
                    thumb_size = "width=300&height=300"
                    thumb_parameters = f"url={thumb_url}&quality=90&format=jpeg&X-Plex-Token={self._plex_token}"
                    thumb = (
                        f"{self._plexamp_entity.server.get("uri")}/photo/:/transcode?{thumb_size}&{thumb_parameters}"
                        if thumb_url
                        else None
                    )

                    device_information["thumb"] = thumb
                    device_information["title"] = currently_playing_metadata.get(
                        "title"
                    )
                    device_information["parent_title"] = currently_playing_metadata.get(
                        "parentTitle"
                    )
                    device_information["grandparent_title"] = (
                        currently_playing_metadata.get("grandparentTitle")
                    )
                    return device_information
            return device_information

        except aiohttp.ClientError | aiohttp.ServerTimeoutError as e:
            _LOGGER.error(
                "Couldn't update metadata for %s: %s. Error: %s",
                self._device_name,
                play_queue_url,
                e,
            )
