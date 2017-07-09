"""Tests for Wake On LAN component."""
import asyncio
from functools import partial
from unittest import mock

import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components.wake_on_lan import (
    DOMAIN, SERVICE_SEND_MAGIC_PACKET)


@pytest.fixture
def mock_wakeonlan():
    """Mock mock_wakeonlan."""
    module = mock.MagicMock()
    with mock.patch.dict('sys.modules', {
        'wakeonlan': module,
    }):
        yield module


@asyncio.coroutine
def test_send_magic_packet(hass, caplog, mock_wakeonlan):
    """Test of send magic packet service call."""
    mac = "aa:bb:cc:dd:ee:ff"
    bc_ip = "192.168.255.255"

    yield from async_setup_component(hass, DOMAIN, {})

    yield from hass.async_add_job(
        hass.services.call, DOMAIN, SERVICE_SEND_MAGIC_PACKET,
        {"mac": mac, "broadcast_address": bc_ip})
    assert len(mock_wakeonlan.mock_calls) == 1
    assert mock_wakeonlan.mock_calls[-1][1][0] == mac
    assert mock_wakeonlan.mock_calls[-1][2]['ip_address'] == bc_ip

    yield from hass.async_add_job(
        hass.services.call,
        DOMAIN, SERVICE_SEND_MAGIC_PACKET,
        {"broadcast_address": bc_ip})
    assert 'ERROR' in caplog.text
    assert len(mock_wakeonlan.mock_calls) == 1

    yield from hass.async_add_job(
        hass.services.call, DOMAIN, SERVICE_SEND_MAGIC_PACKET, {"mac": mac})
    assert len(mock_wakeonlan.mock_calls) == 2
    assert mock_wakeonlan.mock_calls[-1][1][0] == mac
    assert not mock_wakeonlan.mock_calls[-1][2]
