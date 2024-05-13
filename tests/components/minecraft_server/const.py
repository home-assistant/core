"""Constants for Minecraft Server integration tests."""
from mcstatus.motd import Motd
from mcstatus.status_response import (
    JavaStatusPlayers,
    JavaStatusResponse,
    JavaStatusVersion,
)

TEST_HOST = "mc.dummyserver.com"

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
