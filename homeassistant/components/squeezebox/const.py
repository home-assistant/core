"""Constants for the Squeezebox component."""

CONF_HTTPS = "https"
DISCOVERY_TASK = "discovery_task"
DOMAIN = "squeezebox"
DEFAULT_PORT = 9000
KNOWN_PLAYERS = "known_players"
KNOWN_SERVERS = "known_servers"
MANUFACTURER = "https://lyrion.org/"
PLAYER_DISCOVERY_UNSUB = "player_discovery_unsub"
SENSOR_UPDATE_INTERVAL = 60
SERVER_MODEL = "Lyrion Music Server"
STATUS_API_TIMEOUT = 10
STATUS_SENSOR_LASTSCAN = "lastscan"
STATUS_SENSOR_NEEDSRESTART = "needsrestart"
STATUS_SENSOR_NEWVERSION = "newversion"
STATUS_SENSOR_NEWPLUGINS = "newplugins"
STATUS_SENSOR_RESCAN = "rescan"
STATUS_SENSOR_INFO_TOTAL_ALBUMS = "info total albums"
STATUS_SENSOR_INFO_TOTAL_ARTISTS = "info total artists"
STATUS_SENSOR_INFO_TOTAL_DURATION = "info total duration"
STATUS_SENSOR_INFO_TOTAL_GENRES = "info total genres"
STATUS_SENSOR_INFO_TOTAL_SONGS = "info total songs"
STATUS_SENSOR_PLAYER_COUNT = "player count"
STATUS_SENSOR_OTHER_PLAYER_COUNT = "other player count"
STATUS_QUERY_LIBRARYNAME = "libraryname"
STATUS_QUERY_MAC = "mac"
STATUS_QUERY_UUID = "uuid"
STATUS_QUERY_VERSION = "version"
SQUEEZEBOX_SOURCE_STRINGS = (
    "source:",
    "wavin:",
    "spotify:",
    "loop:",
)
SIGNAL_PLAYER_DISCOVERED = "squeezebox_player_discovered"
SIGNAL_PLAYER_REDISCOVERED = "squeezebox_player_rediscovered"
DISCOVERY_INTERVAL = 60
PLAYER_UPDATE_INTERVAL = 5
CONF_BROWSE_LIMIT = "browse_limit"
CONF_VOLUME_STEP = "volume_step"
DEFAULT_BROWSE_LIMIT = 1000
DEFAULT_VOLUME_STEP = 5
ATTR_ANNOUNCE_VOLUME = "announce_volume"
ATTR_ANNOUNCE_TIMEOUT = "announce_timeout"
UNPLAYABLE_TYPES = ("text", "actions")
