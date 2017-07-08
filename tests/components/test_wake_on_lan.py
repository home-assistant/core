"""Tests for Wake On LAN component."""
import asyncio
from functools import partial
from unittest import mock

import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components.wake_on_lan import DOMAIN


@pytest.fixture
def mock_wakeonlan():
    """Mock mock_wakeonlan."""
    module = mock.MagicMock()
    with mock.patch.dict('sys.modules', {
        'wakeonlan': module,
    }):
        yield module


@asyncio.coroutine
def test_setup_component(hass):
    """Test the set up of new component."""
    assert(not hass.services.has_service('wake_on_lan', 'send_magic_packet'))
    yield from async_setup_component(hass, DOMAIN, {})
    assert(hass.services.has_service('wake_on_lan', 'send_magic_packet'))


@asyncio.coroutine
def test_send_magic_packet(hass, caplog, mock_wakeonlan):
    """Test of send magic packet service call."""
    yield from async_setup_component(hass, DOMAIN, {})

    yield from hass.async_add_job(partial(
        hass.services.call, 'wake_on_lan', 'send_magic_packet',
        {"broadcast_address": "192.168.255.255"}))
    assert len(mock_wakeonlan.mock_calls) == 0
    assert 'ERROR' in caplog.text

    yield from hass.async_add_job(partial(
        hass.services.call, 'wake_on_lan', 'send_magic_packet',
        {"mac": "aa:bb:cc:dd:ee:ff"}))
    assert len(mock_wakeonlan.mock_calls) == 1
    assert 'Event service_executed' in caplog.text.splitlines()[-1]

    yield from hass.async_add_job(partial(
        hass.services.call, 'wake_on_lan', 'send_magic_packet',
        {"mac": "aa:bb:cc:dd:ee:ff",
         "broadcast_address": "192.168.255.255"}))
    assert len(mock_wakeonlan.mock_calls) == 2
    assert 'Event service_executed' in caplog.text.splitlines()[-1]
