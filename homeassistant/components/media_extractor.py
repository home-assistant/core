"""
Decorator service for the media_player.play_media service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/media_extractor/
"""
import logging
import os

from homeassistant.components.media_player import (
    ATTR_ENTITY_ID, ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN, MEDIA_PLAYER_PLAY_MEDIA_SCHEMA,
    SERVICE_PLAY_MEDIA)
from homeassistant.config import load_yaml_config_file

REQUIREMENTS = ['youtube_dl==2017.7.9']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'media_extractor'
DEPENDENCIES = ['media_player']

CONF_CUSTOMIZE_ENTITIES = 'customize'
CONF_DEFAULT_STREAM_FORMAT = 'default_format'
DEFAULT_STREAM_FORMAT = 'best'


def setup(hass, config):
    """Set up the media extractor service."""
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__),
                     'media_player', 'services.yaml'))

    def play_media(call):
        """Get stream URL and send it to the media_player.play_media."""
        media_url = call.data.get(ATTR_MEDIA_CONTENT_ID)

        try:
            stream_selector = get_stream_query_selector(media_url)
        except YDNetworkException:
            _LOGGER.error("Could not retrieve data for the URL: %s",
                          media_url)
            return

        media_content_type = call.data.get(ATTR_MEDIA_CONTENT_TYPE)
        default_stream_format = config[DOMAIN].get(
            CONF_DEFAULT_STREAM_FORMAT, DEFAULT_STREAM_FORMAT)
        entities_config = config[DOMAIN].get(CONF_CUSTOMIZE_ENTITIES, {})
        entities = call.data.get(ATTR_ENTITY_ID, [])

        if len(entities) == 0:
            pass

        for entity_id in entities:
            stream_format_query = entities_config.get(
                entity_id, {}).get(media_content_type, default_stream_format)

            try:
                stream_url = stream_selector(stream_format_query)
            except YDQueryException:
                continue
            else:
                data = {k: v for k, v in call.data.items()
                        if k != ATTR_MEDIA_CONTENT_ID and k != ATTR_ENTITY_ID}
                data[ATTR_MEDIA_CONTENT_ID] = stream_url
                data[ATTR_ENTITY_ID] = entity_id

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


class YDNetworkException(Exception):
    """Media extractor network exception."""

    pass


class YDQueryException(Exception):
    """Media extractor query exception."""

    pass


def get_stream_query_selector(media_url):
    """Extract stream URL from the media URL."""
    from youtube_dl import YoutubeDL
    from youtube_dl.utils import DownloadError, ExtractorError

    ydl = YoutubeDL({'quiet': True, 'logger': _LOGGER})

    try:
        all_media_streams = ydl.extract_info(media_url, process=False)
    except DownloadError:
        # This exception will be logged by youtube-dl itself
        raise YDNetworkException()

    if 'entries' in all_media_streams:
        _LOGGER.warning("Playlists are not supported, "
                        "looking for the first video")
        try:
            selected_stream = next(all_media_streams['entries'])
        except StopIteration:
            _LOGGER.error("Playlist is empty")
            raise YDNetworkException()
    else:
        selected_stream = all_media_streams

    try:
        media_info = ydl.process_ie_result(selected_stream, download=False)
    except (ExtractorError, DownloadError):
        # This exception will be logged by youtube-dl itself
        raise YDNetworkException()

    def stream_query_selector(stream_format_query):
        """Find stream url that match stream_format_query."""
        try:
            format_selector = ydl.build_format_selector(stream_format_query)
        except (SyntaxError, ValueError) as e:
            _LOGGER.error(e)
            raise YDQueryException()

        try:
            queried_stream = next(format_selector(media_info))
        except (KeyError, StopIteration):
            _LOGGER.error("Could not extract stream for the query: %s",
                          stream_format_query)
            raise YDQueryException()

        return queried_stream['url']

    return stream_query_selector
