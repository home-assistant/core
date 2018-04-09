"""The tests for the mailbox component."""
import asyncio
from hashlib import sha1

import pytest

from homeassistant.bootstrap import async_setup_component
import homeassistant.components.mailbox as mailbox


@pytest.fixture
def mock_http_client(hass, aiohttp_client):
    """Start the Hass HTTP component."""
    config = {
        mailbox.DOMAIN: {
            'platform': 'demo'
        }
    }
    hass.loop.run_until_complete(
        async_setup_component(hass, mailbox.DOMAIN, config))
    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@asyncio.coroutine
def test_get_platforms_from_mailbox(mock_http_client):
    """Get platforms from mailbox."""
    url = "/api/mailbox/platforms"

    req = yield from mock_http_client.get(url)
    assert req.status == 200
    result = yield from req.json()
    assert len(result) == 1 and "DemoMailbox" in result


@asyncio.coroutine
def test_get_messages_from_mailbox(mock_http_client):
    """Get messages from mailbox."""
    url = "/api/mailbox/messages/DemoMailbox"

    req = yield from mock_http_client.get(url)
    assert req.status == 200
    result = yield from req.json()
    assert len(result) == 10


@asyncio.coroutine
def test_get_media_from_mailbox(mock_http_client):
    """Get audio from mailbox."""
    mp3sha = "3f67c4ea33b37d1710f772a26dd3fb43bb159d50"
    msgtxt = ("Message 1. "
              "Lorem ipsum dolor sit amet, consectetur adipiscing elit. ")
    msgsha = sha1(msgtxt.encode('utf-8')).hexdigest()

    url = "/api/mailbox/media/DemoMailbox/%s" % (msgsha)
    req = yield from mock_http_client.get(url)
    assert req.status == 200
    data = yield from req.read()
    assert sha1(data).hexdigest() == mp3sha


@asyncio.coroutine
def test_delete_from_mailbox(mock_http_client):
    """Get audio from mailbox."""
    msgtxt1 = ("Message 1. "
               "Lorem ipsum dolor sit amet, consectetur adipiscing elit. ")
    msgtxt2 = ("Message 3. "
               "Lorem ipsum dolor sit amet, consectetur adipiscing elit. ")
    msgsha1 = sha1(msgtxt1.encode('utf-8')).hexdigest()
    msgsha2 = sha1(msgtxt2.encode('utf-8')).hexdigest()

    for msg in [msgsha1, msgsha2]:
        url = "/api/mailbox/delete/DemoMailbox/%s" % (msg)
        req = yield from mock_http_client.delete(url)
        assert req.status == 200

    url = "/api/mailbox/messages/DemoMailbox"
    req = yield from mock_http_client.get(url)
    assert req.status == 200
    result = yield from req.json()
    assert len(result) == 8


@asyncio.coroutine
def test_get_messages_from_invalid_mailbox(mock_http_client):
    """Get messages from mailbox."""
    url = "/api/mailbox/messages/mailbox.invalid_mailbox"

    req = yield from mock_http_client.get(url)
    assert req.status == 404


@asyncio.coroutine
def test_get_media_from_invalid_mailbox(mock_http_client):
    """Get messages from mailbox."""
    msgsha = "0000000000000000000000000000000000000000"
    url = "/api/mailbox/media/mailbox.invalid_mailbox/%s" % (msgsha)

    req = yield from mock_http_client.get(url)
    assert req.status == 404


@asyncio.coroutine
def test_get_media_from_invalid_msgid(mock_http_client):
    """Get messages from mailbox."""
    msgsha = "0000000000000000000000000000000000000000"
    url = "/api/mailbox/media/DemoMailbox/%s" % (msgsha)

    req = yield from mock_http_client.get(url)
    assert req.status == 500


@asyncio.coroutine
def test_delete_from_invalid_mailbox(mock_http_client):
    """Get audio from mailbox."""
    msgsha = "0000000000000000000000000000000000000000"
    url = "/api/mailbox/delete/mailbox.invalid_mailbox/%s" % (msgsha)

    req = yield from mock_http_client.delete(url)
    assert req.status == 404
