"""Constants for the Devialet integration."""

from collections.abc import Mapping
from typing import Final

DOMAIN: Final = "devialet"
MANUFACTURER: Final = "Devialet"

SOUND_MODES = {
    "Custom": "custom",
    "Flat": "flat",
    "Night mode": "night mode",
    "Voice": "voice",
}

# Translation of MediaMetadata keys to DIDL-Lite keys.
# See https://developers.google.com/cast/docs/reference/messages#MediaData via
# https://www.home-assistant.io/integrations/media_player/ for HA keys.
# See http://www.upnp.org/specs/av/UPnP-av-ContentDirectory-v4-Service.pdf for
# DIDL-Lite keys.
MEDIA_METADATA_DIDL: Mapping[str, str] = {
    "subtitle": "longDescription",
    "releaseDate": "date",
    "studio": "publisher",
    "season": "episodeSeason",
    "episode": "episodeNumber",
    "albumName": "album",
    "trackNumber": "originalTrackNumber",
}
