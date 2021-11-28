"""Const for Sonos."""
import datetime

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_COMPOSER,
    MEDIA_CLASS_CONTRIBUTING_ARTIST,
    MEDIA_CLASS_GENRE,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_TRACK,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_COMPOSER,
    MEDIA_TYPE_CONTRIBUTING_ARTIST,
    MEDIA_TYPE_GENRE,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

UPNP_ST = "urn:schemas-upnp-org:device:ZonePlayer:1"

DOMAIN = "sonos"
DATA_SONOS = "sonos_media_player"
DATA_SONOS_DISCOVERY_MANAGER = "sonos_discovery_manager"
PLATFORMS = {BINARY_SENSOR_DOMAIN, MP_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN}

SONOS_ARTIST = "artists"
SONOS_ALBUM = "albums"
SONOS_PLAYLISTS = "playlists"
SONOS_GENRE = "genres"
SONOS_ALBUM_ARTIST = "album_artists"
SONOS_TRACKS = "tracks"
SONOS_COMPOSER = "composers"

SONOS_STATE_PLAYING = "PLAYING"
SONOS_STATE_TRANSITIONING = "TRANSITIONING"

EXPANDABLE_MEDIA_TYPES = [
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_COMPOSER,
    MEDIA_TYPE_GENRE,
    MEDIA_TYPE_PLAYLIST,
    SONOS_ALBUM,
    SONOS_ALBUM_ARTIST,
    SONOS_ARTIST,
    SONOS_GENRE,
    SONOS_COMPOSER,
    SONOS_PLAYLISTS,
]

SONOS_TO_MEDIA_CLASSES = {
    SONOS_ALBUM: MEDIA_CLASS_ALBUM,
    SONOS_ALBUM_ARTIST: MEDIA_CLASS_ARTIST,
    SONOS_ARTIST: MEDIA_CLASS_CONTRIBUTING_ARTIST,
    SONOS_COMPOSER: MEDIA_CLASS_COMPOSER,
    SONOS_GENRE: MEDIA_CLASS_GENRE,
    SONOS_PLAYLISTS: MEDIA_CLASS_PLAYLIST,
    SONOS_TRACKS: MEDIA_CLASS_TRACK,
    "object.container.album.musicAlbum": MEDIA_CLASS_ALBUM,
    "object.container.genre.musicGenre": MEDIA_CLASS_PLAYLIST,
    "object.container.person.composer": MEDIA_CLASS_PLAYLIST,
    "object.container.person.musicArtist": MEDIA_CLASS_ARTIST,
    "object.container.playlistContainer.sameArtist": MEDIA_CLASS_ARTIST,
    "object.container.playlistContainer": MEDIA_CLASS_PLAYLIST,
    "object.item.audioItem.musicTrack": MEDIA_CLASS_TRACK,
}

SONOS_TO_MEDIA_TYPES = {
    SONOS_ALBUM: MEDIA_TYPE_ALBUM,
    SONOS_ALBUM_ARTIST: MEDIA_TYPE_ARTIST,
    SONOS_ARTIST: MEDIA_TYPE_CONTRIBUTING_ARTIST,
    SONOS_COMPOSER: MEDIA_TYPE_COMPOSER,
    SONOS_GENRE: MEDIA_TYPE_GENRE,
    SONOS_PLAYLISTS: MEDIA_TYPE_PLAYLIST,
    SONOS_TRACKS: MEDIA_TYPE_TRACK,
    "object.container.album.musicAlbum": MEDIA_TYPE_ALBUM,
    "object.container.genre.musicGenre": MEDIA_TYPE_PLAYLIST,
    "object.container.person.composer": MEDIA_TYPE_PLAYLIST,
    "object.container.person.musicArtist": MEDIA_TYPE_ARTIST,
    "object.container.playlistContainer.sameArtist": MEDIA_TYPE_ARTIST,
    "object.container.playlistContainer": MEDIA_TYPE_PLAYLIST,
    "object.item.audioItem.musicTrack": MEDIA_TYPE_TRACK,
}

MEDIA_TYPES_TO_SONOS = {
    MEDIA_TYPE_ALBUM: SONOS_ALBUM,
    MEDIA_TYPE_ARTIST: SONOS_ALBUM_ARTIST,
    MEDIA_TYPE_CONTRIBUTING_ARTIST: SONOS_ARTIST,
    MEDIA_TYPE_COMPOSER: SONOS_COMPOSER,
    MEDIA_TYPE_GENRE: SONOS_GENRE,
    MEDIA_TYPE_PLAYLIST: SONOS_PLAYLISTS,
    MEDIA_TYPE_TRACK: SONOS_TRACKS,
}

SONOS_TYPES_MAPPING = {
    "A:ALBUM": SONOS_ALBUM,
    "A:ALBUMARTIST": SONOS_ALBUM_ARTIST,
    "A:ARTIST": SONOS_ARTIST,
    "A:COMPOSER": SONOS_COMPOSER,
    "A:GENRE": SONOS_GENRE,
    "A:PLAYLISTS": SONOS_PLAYLISTS,
    "A:TRACKS": SONOS_TRACKS,
    "object.container.album.musicAlbum": SONOS_ALBUM,
    "object.container.genre.musicGenre": SONOS_GENRE,
    "object.container.person.composer": SONOS_COMPOSER,
    "object.container.person.musicArtist": SONOS_ALBUM_ARTIST,
    "object.container.playlistContainer.sameArtist": SONOS_ARTIST,
    "object.container.playlistContainer": SONOS_PLAYLISTS,
    "object.item.audioItem.musicTrack": SONOS_TRACKS,
}

LIBRARY_TITLES_MAPPING = {
    "A:ALBUM": "Albums",
    "A:ALBUMARTIST": "Artists",
    "A:ARTIST": "Contributing Artists",
    "A:COMPOSER": "Composers",
    "A:GENRE": "Genres",
    "A:PLAYLISTS": "Playlists",
    "A:TRACKS": "Tracks",
}

PLAYABLE_MEDIA_TYPES = [
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_COMPOSER,
    MEDIA_TYPE_CONTRIBUTING_ARTIST,
    MEDIA_TYPE_GENRE,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
]

SONOS_CHECK_ACTIVITY = "sonos_check_activity"
SONOS_CREATE_ALARM = "sonos_create_alarm"
SONOS_CREATE_BATTERY = "sonos_create_battery"
SONOS_CREATE_SWITCHES = "sonos_create_switches"
SONOS_CREATE_MEDIA_PLAYER = "sonos_create_media_player"
SONOS_ENTITY_CREATED = "sonos_entity_created"
SONOS_POLL_UPDATE = "sonos_poll_update"
SONOS_ALARMS_UPDATED = "sonos_alarms_updated"
SONOS_FAVORITES_UPDATED = "sonos_favorites_updated"
SONOS_SPEAKER_ACTIVITY = "sonos_speaker_activity"
SONOS_SPEAKER_ADDED = "sonos_speaker_added"
SONOS_STATE_UPDATED = "sonos_state_updated"
SONOS_REBOOTED = "sonos_rebooted"

SOURCE_LINEIN = "Line-in"
SOURCE_TV = "TV"

AVAILABILITY_CHECK_INTERVAL = datetime.timedelta(minutes=1)
AVAILABILITY_TIMEOUT = AVAILABILITY_CHECK_INTERVAL.total_seconds() * 4.5
BATTERY_SCAN_INTERVAL = datetime.timedelta(minutes=15)
SCAN_INTERVAL = datetime.timedelta(seconds=10)
DISCOVERY_INTERVAL = datetime.timedelta(seconds=60)
SUBSCRIPTION_TIMEOUT = 1200
