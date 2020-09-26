"""The tests for the mailbox component."""
from hashlib import sha1

import pytest

from homeassistant.bootstrap import async_setup_component
import homeassistant.components.mailbox as mailbox
from homeassistant.const import HTTP_INTERNAL_SERVER_ERROR, HTTP_NOT_FOUND


@pytest.fixture
def mock_http_client(hass, hass_client):
    """Start the Home Assistant HTTP component."""
    config = {mailbox.DOMAIN: {"platform": "demo"}}
    hass.loop.run_until_complete(async_setup_component(hass, mailbox.DOMAIN, config))
    return hass.loop.run_until_complete(hass_client())


async def test_get_platforms_from_mailbox(mock_http_client):
    """Get platforms from mailbox."""
    url = "/api/mailbox/platforms"

    req = await mock_http_client.get(url)
    assert req.status == 200
    result = await req.json()
    assert len(result) == 1 and "DemoMailbox" == result[0].get("name", None)


async def test_get_messages_from_mailbox(mock_http_client):
    """Get messages from mailbox."""
    url = "/api/mailbox/messages/DemoMailbox"

    req = await mock_http_client.get(url)
    assert req.status == 200
    result = await req.json()
    assert len(result) == 10


async def test_get_media_from_mailbox(mock_http_client):
    """Get audio from mailbox."""
    mp3sha = "3f67c4ea33b37d1710f772a26dd3fb43bb159d50"
    msgtxt = "Message 1. Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    msgsha = sha1(msgtxt.encode("utf-8")).hexdigest()

    url = "/api/mailbox/media/DemoMailbox/%s" % (msgsha)
    req = await mock_http_client.get(url)
    assert req.status == 200
    data = await req.read()
    assert sha1(data).hexdigest() == mp3sha


async def test_delete_from_mailbox(mock_http_client):
    """Get audio from mailbox."""
    msgtxt1 = "Message 1. Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    msgtxt2 = "Message 3. Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    msgsha1 = sha1(msgtxt1.encode("utf-8")).hexdigest()
    msgsha2 = sha1(msgtxt2.encode("utf-8")).hexdigest()

    for msg in [msgsha1, msgsha2]:
        url = "/api/mailbox/delete/DemoMailbox/%s" % (msg)
        req = await mock_http_client.delete(url)
        assert req.status == 200

    url = "/api/mailbox/messages/DemoMailbox"
    req = await mock_http_client.get(url)
    assert req.status == 200
    result = await req.json()
    assert len(result) == 8


async def test_get_messages_from_invalid_mailbox(mock_http_client):
    """Get messages from mailbox."""
    url = "/api/mailbox/messages/mailbox.invalid_mailbox"

    req = await mock_http_client.get(url)
    assert req.status == HTTP_NOT_FOUND


async def test_get_media_from_invalid_mailbox(mock_http_client):
    """Get messages from mailbox."""
    msgsha = "0000000000000000000000000000000000000000"
    url = "/api/mailbox/media/mailbox.invalid_mailbox/%s" % (msgsha)

    req = await mock_http_client.get(url)
    assert req.status == HTTP_NOT_FOUND


async def test_get_media_from_invalid_msgid(mock_http_client):
    """Get messages from mailbox."""
    msgsha = "0000000000000000000000000000000000000000"
    url = "/api/mailbox/media/DemoMailbox/%s" % (msgsha)

    req = await mock_http_client.get(url)
    assert req.status == HTTP_INTERNAL_SERVER_ERROR


async def test_delete_from_invalid_mailbox(mock_http_client):
    """Get audio from mailbox."""
    msgsha = "0000000000000000000000000000000000000000"
    url = "/api/mailbox/delete/mailbox.invalid_mailbox/%s" % (msgsha)

    req = await mock_http_client.delete(url)
    assert req.status == HTTP_NOT_FOUND
