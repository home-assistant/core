"""Constants for ezbeq tests."""

from homeassistant.components.ezbeq.const import (
    CONF_CODEC_EXTENDED_SENSOR,
    CONF_CODEC_SENSOR,
    CONF_EDITION_SENSOR,
    CONF_JELLYFIN_CODEC_SENSOR,
    CONF_JELLYFIN_DISPLAY_TITLE_SENSOR,
    CONF_JELLYFIN_LAYOUT_SENSOR,
    CONF_JELLYFIN_PROFILE_SENSOR,
    CONF_PREFERRED_AUTHOR,
    CONF_SOURCE_MEDIA_PLAYER,
    CONF_SOURCE_TYPE,
    CONF_TITLE_SENSOR,
    CONF_TMDB_SENSOR,
    CONF_YEAR_SENSOR,
)
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_CONFIG = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 8080,
    CONF_SOURCE_TYPE: "Plex",
    CONF_SOURCE_MEDIA_PLAYER: "media_player.living_room",
    CONF_TMDB_SENSOR: "sensor.tmdb",
    CONF_YEAR_SENSOR: "sensor.year",
    CONF_CODEC_SENSOR: "sensor.codec",
    CONF_CODEC_EXTENDED_SENSOR: "sensor.codec_extended",
    CONF_EDITION_SENSOR: "sensor.edition",
    CONF_TITLE_SENSOR: "sensor.title",
    CONF_PREFERRED_AUTHOR: "",
}


JF_MOCK_CONFIG = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 8080,
    CONF_SOURCE_TYPE: "Jellyfin",
    CONF_SOURCE_MEDIA_PLAYER: "media_player.living_room",
    CONF_TMDB_SENSOR: "sensor.tmdb",
    CONF_YEAR_SENSOR: "sensor.year",
    CONF_JELLYFIN_CODEC_SENSOR: "sensor.jellyfin_codec",
    CONF_JELLYFIN_DISPLAY_TITLE_SENSOR: "sensor.jellyfin_display_title",
    CONF_JELLYFIN_PROFILE_SENSOR: "sensor.jellyfin_profile",
    CONF_JELLYFIN_LAYOUT_SENSOR: "sensor.jellyfin_layout",
    CONF_EDITION_SENSOR: "sensor.edition",
    CONF_TITLE_SENSOR: "sensor.title",
    CONF_PREFERRED_AUTHOR: "",
}
