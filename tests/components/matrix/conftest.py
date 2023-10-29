"""Define fixtures available for all tests."""
from __future__ import annotations

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
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events

TEST_NOTIFIER_NAME = "matrix_notify"

TEST_DEFAULT_ROOM = "!DefaultNotificationRoom:example.com"
TEST_JOINABLE_ROOMS = ["!RoomIdString:example.com", "#RoomAliasString:example.com"]
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

    async def join(self, room_id: RoomID):
        if room_id in TEST_JOINABLE_ROOMS:
            return JoinResponse(room_id=room_id)
        else:
            return JoinError(message="Not allowed to join this room.")

    async def login(self, *args, **kwargs):
        if kwargs.get("password") == TEST_PASSWORD or kwargs.get("token") == TEST_TOKEN:
            self.access_token = TEST_TOKEN
            return LoginResponse(
                access_token=TEST_TOKEN,
                device_id="test_device",
                user_id=TEST_MXID,
            )
        else:
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
        else:
            self.access_token = ""
            return WhoamiError(
                message="Invalid access token passed.", status_code="M_UNKNOWN_TOKEN"
            )

    async def room_send(self, *args, **kwargs):
        if not self.logged_in:
            raise LocalProtocolError
        if kwargs["room_id"] in TEST_JOINABLE_ROOMS:
            return Response()
        else:
            return ErrorResponse(message="Cannot send a message in this room.")

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
        CONF_ROOMS: TEST_JOINABLE_ROOMS,
        CONF_COMMANDS: [
            {
                CONF_WORD: "WordTrigger",
                CONF_NAME: "WordTriggerEventName",
            },
            {
                CONF_EXPRESSION: "My name is (?P<name>.*)",
                CONF_NAME: "ExpressionTriggerEventName",
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
    "!RoomIdString:example.com": {
        "WordTrigger": {
            "word": "WordTrigger",
            "name": "WordTriggerEventName",
            "rooms": ["!RoomIdString:example.com", "#RoomAliasString:example.com"],
        }
    },
    "#RoomAliasString:example.com": {
        "WordTrigger": {
            "word": "WordTrigger",
            "name": "WordTriggerEventName",
            "rooms": ["!RoomIdString:example.com", "#RoomAliasString:example.com"],
        }
    },
}

MOCK_EXPRESSION_COMMANDS = {
    "!RoomIdString:example.com": [
        {
            "expression": re.compile("My name is (?P<name>.*)"),
            "name": "ExpressionTriggerEventName",
            "rooms": ["!RoomIdString:example.com", "#RoomAliasString:example.com"],
        }
    ],
    "#RoomAliasString:example.com": [
        {
            "expression": re.compile("My name is (?P<name>.*)"),
            "name": "ExpressionTriggerEventName",
            "rooms": ["!RoomIdString:example.com", "#RoomAliasString:example.com"],
        }
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
    assert isinstance(matrix_bot := hass.data[MATRIX_DOMAIN], MatrixBot)

    await hass.async_start()

    return matrix_bot


@pytest.fixture
def matrix_events(hass: HomeAssistant):
    """Track event calls."""
    return async_capture_events(hass, MATRIX_DOMAIN)


@pytest.fixture
def command_events(hass: HomeAssistant):
    """Track event calls."""
    return async_capture_events(hass, EVENT_MATRIX_COMMAND)


@pytest.fixture
def image_path(tmp_path):
    """Provide the Path to a mock image."""
    image = Image.new("RGBA", size=(50, 50), color=(256, 0, 0))
    image_file = tempfile.NamedTemporaryFile(dir=tmp_path)
    image.save(image_file, "PNG")
    return image_file
