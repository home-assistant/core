"""Constants for the Minecraft Server integration."""

ATTR_PLAYERS_LIST = "players_list"

DEFAULT_HOST = "localhost:25565"
DEFAULT_NAME = "Minecraft Server"
DEFAULT_PORT = 25565

DOMAIN = "minecraft_server"

ICON_LATENCY = "mdi:signal"
ICON_PLAYERS_MAX = "mdi:account-multiple"
ICON_PLAYERS_ONLINE = "mdi:account-multiple"
ICON_PROTOCOL_VERSION = "mdi:numeric"
ICON_STATUS = "mdi:lan"
ICON_VERSION = "mdi:numeric"
ICON_MOTD = "mdi:minecraft"

KEY_LATENCY = "latency"
KEY_PLAYERS_MAX = "players_max"
KEY_PLAYERS_ONLINE = "players_online"
KEY_PROTOCOL_VERSION = "protocol_version"
KEY_STATUS = "status"
KEY_VERSION = "version"
KEY_MOTD = "motd"

MANUFACTURER = "Mojang AB"

NAME_LATENCY = "Latency Time"
NAME_PLAYERS_MAX = "Players Max"
NAME_PLAYERS_ONLINE = "Players Online"
NAME_PROTOCOL_VERSION = "Protocol Version"
NAME_STATUS = "Status"
NAME_VERSION = "Version"
NAME_MOTD = "World Message"

SCAN_INTERVAL = 60

SIGNAL_NAME_PREFIX = f"signal_{DOMAIN}"

SRV_RECORD_PREFIX = "_minecraft._tcp"

UNIT_PLAYERS_MAX = "players"
UNIT_PLAYERS_ONLINE = "players"
