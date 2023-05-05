"""The tests for the mailbox component."""
from datetime import datetime
from hashlib import sha1
from http import HTTPStatus
from typing import Any

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.bootstrap import async_setup_component
import homeassistant.components.mailbox as mailbox
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from tests.common import MockModule, mock_integration, mock_platform
from tests.typing import ClientSessionGenerator

MAILBOX_NAME = "TestMailbox"
MEDIA_DATA = b"3f67c4ea33b37d1710f"
MESSAGE_TEXT = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "


def _create_message(idx: int) -> dict[str, Any]:
    """Create a sample message."""
    msgtime = dt_util.as_timestamp(datetime(2010, 12, idx + 1, 13, 17, 00))
    msgtxt = f"Message {idx + 1}. {MESSAGE_TEXT}"
    msgsha = sha1(msgtxt.encode("utf-8")).hexdigest()
    return {
        "info": {
            "origtime": int(msgtime),
            "callerid": "John Doe <212-555-1212>",
            "duration": "10",
        },
        "text": msgtxt,
        "sha": msgsha,
    }


class TestMailbox(mailbox.Mailbox):
    """Test Mailbox, with 10 sample messages."""

    def __init__(self, hass: HomeAssistant, name: str) -> None:
        """Initialize Test mailbox."""
        super().__init__(hass, name)
        self._messages: dict[str, dict[str, Any]] = {}
        for idx in range(0, 10):
            msg = _create_message(idx)
            msgsha = msg["sha"]
            self._messages[msgsha] = msg

    @property
    def media_type(self) -> str:
        """Return the supported media type."""
        return mailbox.CONTENT_TYPE_MPEG

    @property
    def can_delete(self) -> bool:
        """Return if messages can be deleted."""
        return True

    @property
    def has_media(self) -> bool:
        """Return if messages have attached media files."""
        return True

    async def async_get_media(self, msgid: str) -> bytes:
        """Return the media blob for the msgid."""
        if msgid not in self._messages:
            raise mailbox.StreamError("Message not found")

        return MEDIA_DATA

    async def async_get_messages(self) -> list[dict[str, Any]]:
        """Return a list of the current messages."""
        return sorted(
            self._messages.values(),
            key=lambda item: item["info"]["origtime"],  # type: ignore[no-any-return]
            reverse=True,
        )

    async def async_delete(self, msgid: str) -> bool:
        """Delete the specified messages."""
        if msgid in self._messages:
            del self._messages[msgid]
        self.async_update()
        return True


class MockMailbox:
    """A mock mailbox platform."""

    async def async_get_handler(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> mailbox.Mailbox:
        """Set up the Test mailbox."""
        return TestMailbox(hass, MAILBOX_NAME)


@pytest.fixture
def mock_mailbox(hass: HomeAssistant) -> None:
    """Mock mailbox."""
    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.mailbox", MockMailbox())


@pytest.fixture
async def mock_http_client(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_mailbox: None
) -> TestClient:
    """Start the Home Assistant HTTP component."""
    assert await async_setup_component(
        hass, mailbox.DOMAIN, {mailbox.DOMAIN: {"platform": "test"}}
    )
    return await hass_client()


async def test_get_platforms_from_mailbox(mock_http_client: TestClient) -> None:
    """Get platforms from mailbox."""
    url = "/api/mailbox/platforms"

    req = await mock_http_client.get(url)
    assert req.status == HTTPStatus.OK
    result = await req.json()
    assert len(result) == 1
    assert result[0].get("name") == "TestMailbox"


async def test_get_messages_from_mailbox(mock_http_client: TestClient) -> None:
    """Get messages from mailbox."""
    url = "/api/mailbox/messages/TestMailbox"

    req = await mock_http_client.get(url)
    assert req.status == HTTPStatus.OK
    result = await req.json()
    assert len(result) == 10


async def test_get_media_from_mailbox(mock_http_client: TestClient) -> None:
    """Get audio from mailbox."""
    mp3sha = "7cad61312c7b66f619295be2da8c7ac73b4968f1"
    msgtxt = "Message 1. Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    msgsha = sha1(msgtxt.encode("utf-8")).hexdigest()

    url = f"/api/mailbox/media/TestMailbox/{msgsha}"
    req = await mock_http_client.get(url)
    assert req.status == HTTPStatus.OK
    data = await req.read()
    assert sha1(data).hexdigest() == mp3sha


async def test_delete_from_mailbox(mock_http_client: TestClient) -> None:
    """Get audio from mailbox."""
    msgtxt1 = "Message 1. Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    msgtxt2 = "Message 3. Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    msgsha1 = sha1(msgtxt1.encode("utf-8")).hexdigest()
    msgsha2 = sha1(msgtxt2.encode("utf-8")).hexdigest()

    for msg in [msgsha1, msgsha2]:
        url = f"/api/mailbox/delete/TestMailbox/{msg}"
        req = await mock_http_client.delete(url)
        assert req.status == HTTPStatus.OK

    url = "/api/mailbox/messages/TestMailbox"
    req = await mock_http_client.get(url)
    assert req.status == HTTPStatus.OK
    result = await req.json()
    assert len(result) == 8


async def test_get_messages_from_invalid_mailbox(mock_http_client: TestClient) -> None:
    """Get messages from mailbox."""
    url = "/api/mailbox/messages/mailbox.invalid_mailbox"

    req = await mock_http_client.get(url)
    assert req.status == HTTPStatus.NOT_FOUND


async def test_get_media_from_invalid_mailbox(mock_http_client: TestClient) -> None:
    """Get messages from mailbox."""
    msgsha = "0000000000000000000000000000000000000000"
    url = f"/api/mailbox/media/mailbox.invalid_mailbox/{msgsha}"

    req = await mock_http_client.get(url)
    assert req.status == HTTPStatus.NOT_FOUND


async def test_get_media_from_invalid_msgid(mock_http_client: TestClient) -> None:
    """Get messages from mailbox."""
    msgsha = "0000000000000000000000000000000000000000"
    url = f"/api/mailbox/media/TestMailbox/{msgsha}"

    req = await mock_http_client.get(url)
    assert req.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_delete_from_invalid_mailbox(mock_http_client: TestClient) -> None:
    """Get audio from mailbox."""
    msgsha = "0000000000000000000000000000000000000000"
    url = f"/api/mailbox/delete/mailbox.invalid_mailbox/{msgsha}"

    req = await mock_http_client.delete(url)
    assert req.status == HTTPStatus.NOT_FOUND
