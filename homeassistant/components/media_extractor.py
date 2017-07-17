"""
Decorator service for the media_player.play_media service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/media_extractor/
"""
import logging
import os

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID, DOMAIN as MEDIA_PLAYER_DOMAIN,
    MEDIA_PLAYER_PLAY_MEDIA_SCHEMA, SERVICE_PLAY_MEDIA)
from homeassistant.config import load_yaml_config_file

REQUIREMENTS = ['youtube_dl==2017.7.9']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'media_extractor'
DEPENDENCIES = ['media_player']


def setup(hass, config):
    """Set up the media extractor service."""
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__),
                     'media_player', 'services.yaml'))

    def play_media(call):
        """Get stream URL and send it to the media_player.play_media."""
        media_url = call.data.get(ATTR_MEDIA_CONTENT_ID)

        try:
            stream_url = get_media_stream_url(media_url)
        except YDException:
            _LOGGER.error("Could not retrieve data for the URL: %s",
                          media_url)
            return
        else:
            data = {k: v for k, v in call.data.items()
                    if k != ATTR_MEDIA_CONTENT_ID}
            data[ATTR_MEDIA_CONTENT_ID] = stream_url

            hass.async_add_job(
                hass.services.async_call(
                    MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, data)
            )

    hass.services.register(DOMAIN,
                           SERVICE_PLAY_MEDIA,
                           play_media,
                           description=descriptions[SERVICE_PLAY_MEDIA],
                           schema=MEDIA_PLAYER_PLAY_MEDIA_SCHEMA)

    return True


class YDException(Exception):
    """General service exception."""

    pass


def get_media_stream_url(media_url):
    """Extract stream URL from the media URL."""
    from youtube_dl import YoutubeDL
    from youtube_dl.utils import DownloadError, ExtractorError

    ydl = YoutubeDL({'quiet': True, 'logger': _LOGGER})

    try:
        all_media_streams = ydl.extract_info(media_url, process=False)
    except DownloadError:
        # This exception will be logged by youtube-dl itself
        raise YDException()

    if 'entries' in all_media_streams:
        _LOGGER.warning("Playlists are not supported, "
                        "looking for the first video")
        try:
            selected_stream = next(all_media_streams['entries'])
        except StopIteration:
            _LOGGER.error("Playlist is empty")
            raise YDException()
    else:
        selected_stream = all_media_streams

    try:
        media_info = ydl.process_ie_result(selected_stream, download=False)
    except (ExtractorError, DownloadError):
        # This exception will be logged by youtube-dl itself
        raise YDException()

    format_selector = ydl.build_format_selector('best')

    try:
        best_quality_stream = next(format_selector(media_info))
    except (KeyError, StopIteration):
        best_quality_stream = media_info

    return best_quality_stream['url']
