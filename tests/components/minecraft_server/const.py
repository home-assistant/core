"""Constants for Minecraft Server integration tests."""
from mcstatus.motd import Motd
from mcstatus.status_response import (
    BedrockStatusPlayers,
    BedrockStatusResponse,
    BedrockStatusVersion,
    JavaStatusPlayers,
    JavaStatusResponse,
    JavaStatusVersion,
)

from homeassistant.components.minecraft_server.api import MinecraftServerData

TEST_HOST = "mc.dummyserver.com"
TEST_PORT = 25566
TEST_ADDRESS = f"{TEST_HOST}:{TEST_PORT}"

TEST_JAVA_STATUS_RESPONSE_RAW = {
    "description": {"text": "Dummy Description"},
    "version": {"name": "Dummy Version", "protocol": 123},
    "players": {
        "online": 3,
        "max": 10,
        "sample": [
            {"name": "Player 1", "id": "1"},
            {"name": "Player 2", "id": "2"},
            {"name": "Player 3", "id": "3"},
        ],
    },
}

TEST_JAVA_STATUS_RESPONSE = JavaStatusResponse(
    raw=TEST_JAVA_STATUS_RESPONSE_RAW,
    players=JavaStatusPlayers.build(TEST_JAVA_STATUS_RESPONSE_RAW["players"]),
    version=JavaStatusVersion.build(TEST_JAVA_STATUS_RESPONSE_RAW["version"]),
    motd=Motd.parse(TEST_JAVA_STATUS_RESPONSE_RAW["description"], bedrock=False),
    icon=None,
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
    motd=Motd.parse("Dummy Description", bedrock=True),
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
