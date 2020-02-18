"""Fixtures for component."""

from unittest.mock import patch

import pytest
from tests.common import MockConfigEntry, mock_coro

from homeassistant.components.apple_tv import config_flow
from pyatv import conf

from .common import FlowInteraction, MockPairingHandler, create_conf


@pytest.fixture
def mock_scan():
    """Mock pyatv.scan."""
    with patch("homeassistant.components.apple_tv.config_flow.scan") as mock_scan:

        async def _scan(loop, timeout=5, identifier=None, protocol=None, hosts=None):
            if not mock_scan.hosts:
                mock_scan.hosts = hosts
            return mock_scan.result

        mock_scan.result = []
        mock_scan.hosts = None
        mock_scan.side_effect = _scan
        yield mock_scan


@pytest.fixture
def dmap_pin():
    """Mock pyatv.scan."""
    with patch("homeassistant.components.apple_tv.config_flow.randrange") as mock_pin:
        mock_pin.side_effect = lambda start, stop: 1111
        yield mock_pin


@pytest.fixture
def pairing():
    """Mock pyatv.scan."""
    with patch("homeassistant.components.apple_tv.config_flow.pair") as mock_pair:

        async def _pair(config, protocol, loop, session=None, **kwargs):
            handler = MockPairingHandler(None, config.get_service(protocol))
            handler.always_fail = mock_pair.always_fail
            return handler

        mock_pair.always_fail = False
        mock_pair.side_effect = _pair
        yield mock_pair


@pytest.fixture
def pairing_mock():
    """Mock pyatv.scan."""
    with patch("homeassistant.components.apple_tv.config_flow.pair") as mock_pair:

        async def _pair(config, protocol, loop, session=None, **kwargs):
            return mock_pair

        mock_pair.close.return_value = mock_coro()
        mock_pair.side_effect = _pair
        yield mock_pair


@pytest.fixture
def full_device(mock_scan, dmap_pin):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "MRP Device",
            conf.MrpService("mrp_id", 5555),
            conf.DmapService("dmap_id", None, port=6666),
            conf.AirPlayService("airplay_id", port=7777),
        )
    )
    yield mock_scan


@pytest.fixture
def mrp_device(mock_scan):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf("127.0.0.1", "MRP Device", conf.MrpService("mrp_id", 5555))
    )
    yield mock_scan


@pytest.fixture
def dmap_device(mock_scan):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1", "DMAP Device", conf.DmapService("dmap_id", None, port=6666),
        )
    )
    yield mock_scan


@pytest.fixture
def dmap_device_with_credentials(mock_scan):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "DMAP Device",
            conf.DmapService("dmap_id", "dummy_creds", port=6666),
        )
    )
    yield mock_scan


@pytest.fixture
def airplay_device(mock_scan):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1", "AirPlay Device", conf.AirPlayService("airplay_id", port=7777)
        )
    )
    yield mock_scan


@pytest.fixture
def flow(hass):
    """Return config flow wrapped in FlowInteraction."""
    flow = config_flow.AppleTVConfigFlow()
    flow.hass = hass
    flow.context = {}
    return lambda: FlowInteraction(flow)


@pytest.fixture
def options(hass):
    """Test updating options."""
    entry = MockConfigEntry(
        domain="apple_tv", title="Apple TV", data={}, options={"start_off": False},
    )

    flow = config_flow.AppleTVConfigFlow()
    flow.hass = hass
    flow.context = {}
    options_flow = flow.async_get_options_flow(entry)

    return lambda: FlowInteraction(options_flow)
