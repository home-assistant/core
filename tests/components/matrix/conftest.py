"""Define fixtures available for all tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
import re
import tempfile
from unittest.mock import patch

from nio import (
    AsyncClient,
    ErrorResponse,
    JoinError,
    JoinResponse,
    LocalProtocolError,
    LoginError,
    LoginResponse,
    Response,
    RoomResolveAliasError,
    RoomResolveAliasResponse,
    UploadResponse,
    WhoamiError,
    WhoamiResponse,
)
from PIL import Image
import pytest

from homeassistant.components.matrix import (
    CONF_COMMANDS,
    CONF_EXPRESSION,
    CONF_HOMESERVER,
    CONF_ROOMS,
    CONF_WORD,
    EVENT_MATRIX_COMMAND,
    MatrixBot,
    RoomAlias,
    RoomAnyID,
    RoomID,
)
from homeassistant.components.matrix.const import DOMAIN as MATRIX_DOMAIN
from homeassistant.components.matrix.notify import CONF_DEFAULT_ROOM
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events

TEST_NOTIFIER_NAME = "matrix_notify"

TEST_HOMESERVER = "example.com"
TEST_DEFAULT_ROOM = RoomID("!DefaultNotificationRoom:example.com")
TEST_ROOM_A_ID = RoomID("!RoomA-ID:example.com")
TEST_ROOM_B_ID = RoomID("!RoomB-ID:example.com")
TEST_ROOM_B_ALIAS = RoomAlias("#RoomB-Alias:example.com")
TEST_ROOM_C_ID = RoomID("!RoomC-ID:example.com")
TEST_JOINABLE_ROOMS: dict[RoomAnyID, RoomID] = {
    TEST_ROOM_A_ID: TEST_ROOM_A_ID,
    TEST_ROOM_B_ALIAS: TEST_ROOM_B_ID,
    TEST_ROOM_C_ID: TEST_ROOM_C_ID,
}
TEST_BAD_ROOM = "!UninvitedRoom:example.com"
TEST_MXID = "@user:example.com"
TEST_DEVICE_ID = "FAKEID"
TEST_PASSWORD = "password"
TEST_TOKEN = "access_token"

NIO_IMPORT_PREFIX = "homeassistant.components.matrix.nio."


class _MockAsyncClient(AsyncClient):
    """Mock class to simulate MatrixBot._client's I/O methods."""

    async def close(self):
        return None

    async def room_resolve_alias(self, room_alias: RoomAnyID):
        if room_id := TEST_JOINABLE_ROOMS.get(room_alias):
            return RoomResolveAliasResponse(
                room_alias=room_alias, room_id=room_id, servers=[TEST_HOMESERVER]
            )
        return RoomResolveAliasError(message=f"Could not resolve {room_alias}")

    async def join(self, room_id: RoomID):
        if room_id in TEST_JOINABLE_ROOMS.values():
            return JoinResponse(room_id=room_id)
        return JoinError(message="Not allowed to join this room.")

    async def login(self, *args, **kwargs):
        if kwargs.get("password") == TEST_PASSWORD or kwargs.get("token") == TEST_TOKEN:
            self.access_token = TEST_TOKEN
            return LoginResponse(
                access_token=TEST_TOKEN,
                device_id="test_device",
                user_id=TEST_MXID,
            )
        self.access_token = ""
        return LoginError(message="LoginError", status_code="status_code")

    async def logout(self, *args, **kwargs):
        self.access_token = ""

    async def whoami(self):
        if self.access_token == TEST_TOKEN:
            self.user_id = TEST_MXID
            self.device_id = TEST_DEVICE_ID
            return WhoamiResponse(
                user_id=TEST_MXID, device_id=TEST_DEVICE_ID, is_guest=False
            )
        self.access_token = ""
        return WhoamiError(
            message="Invalid access token passed.", status_code="M_UNKNOWN_TOKEN"
        )

    async def room_send(self, *args, **kwargs):
        if not self.logged_in:
            raise LocalProtocolError
        if kwargs["room_id"] not in TEST_JOINABLE_ROOMS.values():
            return ErrorResponse(message="Cannot send a message in this room.")
        return Response()

    async def sync(self, *args, **kwargs):
        return None

    async def sync_forever(self, *args, **kwargs):
        return None

    async def upload(self, *args, **kwargs):
        return UploadResponse(content_uri="mxc://example.com/randomgibberish"), None


MOCK_CONFIG_DATA = {
    MATRIX_DOMAIN: {
        CONF_HOMESERVER: "https://matrix.example.com",
        CONF_USERNAME: TEST_MXID,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_VERIFY_SSL: True,
        CONF_ROOMS: list(TEST_JOINABLE_ROOMS),
        CONF_COMMANDS: [
            {
                CONF_WORD: "WordTrigger",
                CONF_NAME: "WordTriggerEventName",
            },
            {
                CONF_EXPRESSION: "My name is (?P<name>.*)",
                CONF_NAME: "ExpressionTriggerEventName",
            },
            {
                CONF_WORD: "WordTriggerSubset",
                CONF_NAME: "WordTriggerSubsetEventName",
                CONF_ROOMS: [TEST_ROOM_B_ALIAS, TEST_ROOM_C_ID],
            },
            {
                CONF_EXPRESSION: "Your name is (?P<name>.*)",
                CONF_NAME: "ExpressionTriggerSubsetEventName",
                CONF_ROOMS: [TEST_ROOM_B_ALIAS, TEST_ROOM_C_ID],
            },
        ],
    },
    NOTIFY_DOMAIN: {
        CONF_NAME: TEST_NOTIFIER_NAME,
        CONF_PLATFORM: MATRIX_DOMAIN,
        CONF_DEFAULT_ROOM: TEST_DEFAULT_ROOM,
    },
}

MOCK_WORD_COMMANDS = {
    TEST_ROOM_A_ID: {
        "WordTrigger": {
            "word": "WordTrigger",
            "name": "WordTriggerEventName",
            "rooms": list(TEST_JOINABLE_ROOMS.values()),
        }
    },
    TEST_ROOM_B_ID: {
        "WordTrigger": {
            "word": "WordTrigger",
            "name": "WordTriggerEventName",
            "rooms": list(TEST_JOINABLE_ROOMS.values()),
        },
        "WordTriggerSubset": {
            "word": "WordTriggerSubset",
            "name": "WordTriggerSubsetEventName",
            "rooms": [TEST_ROOM_B_ID, TEST_ROOM_C_ID],
        },
    },
    TEST_ROOM_C_ID: {
        "WordTrigger": {
            "word": "WordTrigger",
            "name": "WordTriggerEventName",
            "rooms": list(TEST_JOINABLE_ROOMS.values()),
        },
        "WordTriggerSubset": {
            "word": "WordTriggerSubset",
            "name": "WordTriggerSubsetEventName",
            "rooms": [TEST_ROOM_B_ID, TEST_ROOM_C_ID],
        },
    },
}

MOCK_EXPRESSION_COMMANDS = {
    TEST_ROOM_A_ID: [
        {
            "expression": re.compile("My name is (?P<name>.*)"),
            "name": "ExpressionTriggerEventName",
            "rooms": list(TEST_JOINABLE_ROOMS.values()),
        }
    ],
    TEST_ROOM_B_ID: [
        {
            "expression": re.compile("My name is (?P<name>.*)"),
            "name": "ExpressionTriggerEventName",
            "rooms": list(TEST_JOINABLE_ROOMS.values()),
        },
        {
            "expression": re.compile("Your name is (?P<name>.*)"),
            "name": "ExpressionTriggerSubsetEventName",
            "rooms": [TEST_ROOM_B_ID, TEST_ROOM_C_ID],
        },
    ],
    TEST_ROOM_C_ID: [
        {
            "expression": re.compile("My name is (?P<name>.*)"),
            "name": "ExpressionTriggerEventName",
            "rooms": list(TEST_JOINABLE_ROOMS.values()),
        },
        {
            "expression": re.compile("Your name is (?P<name>.*)"),
            "name": "ExpressionTriggerSubsetEventName",
            "rooms": [TEST_ROOM_B_ID, TEST_ROOM_C_ID],
        },
    ],
}


@pytest.fixture
def mock_client():
    """Return mocked AsyncClient."""
    with patch("homeassistant.components.matrix.AsyncClient", _MockAsyncClient) as mock:
        yield mock


@pytest.fixture
def mock_save_json():
    """Prevent saving test access_tokens."""
    with patch("homeassistant.components.matrix.save_json") as mock:
        yield mock


@pytest.fixture
def mock_load_json():
    """Mock loading access_tokens from a file."""
    with patch(
        "homeassistant.components.matrix.load_json_object",
        return_value={TEST_MXID: TEST_TOKEN},
    ) as mock:
        yield mock


@pytest.fixture
def mock_allowed_path():
    """Allow using NamedTemporaryFile for mock image."""
    with patch("homeassistant.core.Config.is_allowed_path", return_value=True) as mock:
        yield mock


@pytest.fixture
async def matrix_bot(
    hass: HomeAssistant, mock_client, mock_save_json, mock_allowed_path
) -> MatrixBot:
    """Set up Matrix and Notify component.

    The resulting MatrixBot will have a mocked _client.
    """

    assert await async_setup_component(hass, MATRIX_DOMAIN, MOCK_CONFIG_DATA)
    assert await async_setup_component(hass, NOTIFY_DOMAIN, MOCK_CONFIG_DATA)
    await hass.async_block_till_done()

    # Accessing hass.data in tests is not desirable, but all the tests here
    # currently do this.
    assert isinstance(matrix_bot := hass.data[MATRIX_DOMAIN], MatrixBot)

    await hass.async_start()

    return matrix_bot


@pytest.fixture
def matrix_events(hass: HomeAssistant) -> list[Event]:
    """Track event calls."""
    return async_capture_events(hass, MATRIX_DOMAIN)


@pytest.fixture
def command_events(hass: HomeAssistant) -> list[Event]:
    """Track event calls."""
    return async_capture_events(hass, EVENT_MATRIX_COMMAND)


@pytest.fixture
def image_path(tmp_path: Path) -> Generator[tempfile._TemporaryFileWrapper]:
    """Provide the Path to a mock image."""
    image = Image.new("RGBA", size=(50, 50), color=(256, 0, 0))
    with tempfile.NamedTemporaryFile(dir=tmp_path) as image_file:
        image.save(image_file, "PNG")
        yield image_file
