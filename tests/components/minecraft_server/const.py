"""Constants for Minecraft Server integration tests."""
from mcstatus.motd import Motd
from mcstatus.status_response import (
    BedrockStatusPlayers,
    BedrockStatusResponse,
    BedrockStatusVersion,
    JavaStatusPlayers,
    JavaStatusResponse,
    JavaStatusVersion,
    RawJavaResponse,
    RawJavaResponsePlayer,
    RawJavaResponsePlayers,
    RawJavaResponseVersion,
)

from homeassistant.components.minecraft_server.api import MinecraftServerData

TEST_CONFIG_ENTRY_ID: str = "01234567890123456789012345678901"
TEST_HOST = "mc.dummyserver.com"
TEST_PORT = 25566
TEST_ADDRESS = f"{TEST_HOST}:{TEST_PORT}"

TEST_JAVA_STATUS_RESPONSE_RAW = RawJavaResponse(
    description="Dummy MOTD",
    players=RawJavaResponsePlayers(
        online=3,
        max=10,
        sample=[
            RawJavaResponsePlayer(id="1", name="Player 1"),
            RawJavaResponsePlayer(id="2", name="Player 2"),
            RawJavaResponsePlayer(id="3", name="Player 3"),
        ],
    ),
    version=RawJavaResponseVersion(name="Dummy Version", protocol=123),
    favicon="Dummy Icon",
)

TEST_JAVA_STATUS_RESPONSE = JavaStatusResponse(
    raw=TEST_JAVA_STATUS_RESPONSE_RAW,
    players=JavaStatusPlayers.build(TEST_JAVA_STATUS_RESPONSE_RAW["players"]),
    version=JavaStatusVersion.build(TEST_JAVA_STATUS_RESPONSE_RAW["version"]),
    motd=Motd.parse(TEST_JAVA_STATUS_RESPONSE_RAW["description"], bedrock=False),
    icon=None,
    enforces_secure_chat=False,
    latency=5,
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
