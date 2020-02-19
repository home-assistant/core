"""Fixtures for component."""

from unittest.mock import patch

from pyatv import conf
import pytest

from .common import MockPairingHandler, create_conf

from tests.common import mock_coro


@pytest.fixture(name="mock_scan")
def mock_scan_fixture():
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


@pytest.fixture(name="dmap_pin")
def dmap_pin_fixture():
    """Configure DMAP pin statically to 1111."""
    with patch("homeassistant.components.apple_tv.config_flow.randrange") as mock_pin:
        mock_pin.side_effect = lambda start, stop: 1111
        yield mock_pin


@pytest.fixture(name="pairing_handler")
def pairing_handler_fixture():
    """Return smart pairing handler."""
    with patch("homeassistant.components.apple_tv.config_flow.pair") as mock_pair:

        async def _pair(config, protocol, loop, session=None, **kwargs):
            handler = MockPairingHandler(None, config.get_service(protocol))
            handler.always_fail = mock_pair.always_fail
            return handler

        mock_pair.always_fail = False
        mock_pair.side_effect = _pair
        yield mock_pair


@pytest.fixture(name="pairing_mock")
def pairing_mock_fixture():
    """Mock pyatv.pair."""
    with patch("homeassistant.components.apple_tv.config_flow.pair") as mock_pair:

        async def _pair(config, protocol, loop, session=None, **kwargs):
            return mock_pair

        mock_pair.close.return_value = mock_coro()
        mock_pair.side_effect = _pair
        yield mock_pair


@pytest.fixture(name="full_device")
def full_device_fixture(mock_scan, dmap_pin):
    """Mock device supporting all protocols in scan."""
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


@pytest.fixture(name="mrp_device")
def mrp_device_fixture(mock_scan):
    """Mock device supporting MRP in scan."""
    mock_scan.result.append(
        create_conf("127.0.0.1", "MRP Device", conf.MrpService("mrp_id", 5555))
    )
    yield mock_scan


@pytest.fixture(name="dmap_device")
def dmap_device_fixture(mock_scan):
    """Mock device supporting DMAP in scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1", "DMAP Device", conf.DmapService("dmap_id", None, port=6666),
        )
    )
    yield mock_scan


@pytest.fixture(name="dmap_device_with_credentials")
def dmap_device_with_credentials_fixture(mock_scan):
    """Mock DMAP device with credentials in scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "DMAP Device",
            conf.DmapService("dmap_id", "dummy_creds", port=6666),
        )
    )
    yield mock_scan


@pytest.fixture(name="airplay_device")
def airplay_device_fixture(mock_scan):
    """Mock device supporting AirPlay in scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1", "AirPlay Device", conf.AirPlayService("airplay_id", port=7777)
        )
    )
    yield mock_scan
