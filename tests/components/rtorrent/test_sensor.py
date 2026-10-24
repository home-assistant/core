"""Test rtorrent sensor logging of connection failures."""

from __future__ import annotations

import logging
from unittest.mock import patch
import xmlrpc.client

import pytest

from homeassistant.const import CONF_URL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

URL_WITH_CREDENTIALS = "https://user:secretpassword@localhost/RPC2"
SECRET = "secretpassword"

CONFIG = {
    "sensor": {
        "platform": "rtorrent",
        CONF_URL: URL_WITH_CREDENTIALS,
    }
}


class _FailingServerProxy:
    """Stand in for xmlrpc.client.ServerProxy against a broken daemon.

    ``RTorrentSensor.update`` builds an ``xmlrpc.client.MultiCall`` from the
    proxy and executes it, so the failure has to surface from the multicall,
    exactly as it does against a live daemon.
    """

    def __init__(self) -> None:
        """Initialize the fake server."""
        self.system = _System()


class _System:
    """System endpoint whose multicall fails with a ProtocolError.

    ``ProtocolError`` embeds the request URL, which carries HTTP basic-auth
    credentials, in its repr.
    """

    def multicall(self, calls: list) -> list:
        """Fail like a daemon rejecting the request."""
        raise xmlrpc.client.ProtocolError(URL_WITH_CREDENTIALS, 401, "Unauthorized", {})


@pytest.fixture
async def setup_rtorrent(hass: HomeAssistant) -> None:
    """Set up the rtorrent sensor platform against a failing daemon."""
    with patch("xmlrpc.client.ServerProxy", return_value=_FailingServerProxy()):
        assert await async_setup_component(hass, "sensor", CONFIG)
        await hass.async_block_till_done()


async def test_connection_failure_does_not_leak_credentials(
    hass: HomeAssistant,
    setup_rtorrent: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure the log line for a failed poll never contains the password."""
    caplog.set_level(logging.ERROR)

    await async_update_entity(hass, "sensor.rtorrent_status")

    assert SECRET not in caplog.text
    assert URL_WITH_CREDENTIALS not in caplog.text
    assert hass.states.get("sensor.rtorrent_status").state == STATE_UNAVAILABLE


async def test_connection_failure_still_reports_error_type(
    hass: HomeAssistant,
    setup_rtorrent: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure the failure remains diagnosable without leaking credentials."""
    caplog.set_level(logging.ERROR)

    await async_update_entity(hass, "sensor.rtorrent_status")

    assert "Connection to rtorrent failed (ProtocolError)" in caplog.text
