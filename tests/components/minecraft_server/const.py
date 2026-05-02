"""Constants for Minecraft Server integration tests."""

from mcstatus.motd import Motd
from mcstatus.responses import (
    BedrockStatusPlayers,
    BedrockStatusResponse,
    BedrockStatusVersion,
    JavaStatusPlayer,
    JavaStatusPlayers,
    JavaStatusResponse,
    JavaStatusVersion,
    LegacyStatusPlayers,
    LegacyStatusResponse,
    LegacyStatusVersion,
)

from homeassistant.components.minecraft_server.api import MinecraftServerData

TEST_CONFIG_ENTRY_ID: str = "01234567890123456789012345678901"
TEST_HOST = "mc.dummyserver.com"
TEST_PORT = 25566
TEST_ADDRESS = f"{TEST_HOST}:{TEST_PORT}"

TEST_JAVA_STATUS_RESPONSE = JavaStatusResponse(
    raw={"foo": "bar"},
    players=JavaStatusPlayers(
        online=3,
        max=10,
        sample=[
            JavaStatusPlayer(id="1", name="Player 1"),
            JavaStatusPlayer(id="2", name="Player 2"),
            JavaStatusPlayer(id="3", name="Player 3"),
        ],
    ),
    version=JavaStatusVersion(name="Dummy Version", protocol=123),
    motd=Motd.parse("Dummy MOTD", bedrock=False),
    icon=None,
    enforces_secure_chat=False,
    latency=5,
    forge_data=None,
)

TEST_JAVA_DATA = MinecraftServerData(
    latency=5,
    motd="Dummy MOTD",
    players_max=10,
    players_online=3,
    protocol_version=123,
    version="Dummy Version",
    players_list=["Player 1", "Player 2", "Player 3"],
    edition=None,
    game_mode=None,
    map_name=None,
)

TEST_BEDROCK_STATUS_RESPONSE = BedrockStatusResponse(
    players=BedrockStatusPlayers(online=3, max=10),
    version=BedrockStatusVersion(brand="MCPE", name="Dummy Version", protocol=123),
    motd=Motd.parse("Dummy MOTD", bedrock=True),
    latency=5,
    gamemode="Dummy Game Mode",
    map_name="Dummy Map Name",
)

TEST_BEDROCK_DATA = MinecraftServerData(
    latency=5,
    motd="Dummy MOTD",
    players_max=10,
    players_online=3,
    protocol_version=123,
    version="Dummy Version",
    players_list=None,
    edition="Dummy Edition",
    game_mode="Dummy Game Mode",
    map_name="Dummy Map Name",
)

TEST_LEGACY_JAVA_STATUS_RESPONSE = LegacyStatusResponse(
    players=LegacyStatusPlayers(online=3, max=10),
    version=LegacyStatusVersion(name="1.6.4", protocol=78),
    motd=Motd.parse("Dummy MOTD"),
    latency=5,
)
