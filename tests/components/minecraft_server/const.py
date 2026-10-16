"""Constants for Minecraft Server integration tests."""

from mcstatus.responses import (
    BedrockStatusResponse,
    JavaStatusResponse,
    LegacyStatusResponse,
)

from homeassistant.components.minecraft_server.api import MinecraftServerData

TEST_CONFIG_ENTRY_ID: str = "01234567890123456789012345678901"
TEST_HOST = "mc.dummyserver.com"
TEST_PORT = 25566
TEST_ADDRESS = f"{TEST_HOST}:{TEST_PORT}"

TEST_JAVA_STATUS_RESPONSE = JavaStatusResponse.build(
    {
        "players": {
            "online": 3,
            "max": 10,
            "sample": [
                {"id": "1", "name": "Player 1"},
                {"id": "2", "name": "Player 2"},
                {"id": "3", "name": "Player 3"},
            ],
        },
        "version": {
            "name": "Dummy Version",
            "protocol": 123,
        },
        "description": "Dummy MOTD",
    },
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

TEST_BEDROCK_STATUS_RESPONSE = BedrockStatusResponse.build(
    [
        "MCPE",  # version.brand
        "Dummy MOTD",  # motd
        "123",  # version.protocol
        "Dummy Version",  # version.name
        "3",  # players.online
        "10",  # players.max
        "Dummy Server ID",  # server unique ID
        "Dummy Map Name",  # map_name
        "Dummy Game Mode",  # gamemode
    ],
    latency=5,
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

TEST_LEGACY_JAVA_STATUS_RESPONSE = LegacyStatusResponse.build(
    [
        "78",  # version.protocol
        "1.6.4",  # version.name
        "Dummy MOTD",  # motd
        "3",  # players online
        "10",  # players max
    ],
    latency=5,
)
