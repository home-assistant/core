"""Fixtures for component."""

from unittest.mock import patch

from pyatv import conf
from pyatv.const import PairingRequirement, Protocol
from pyatv.support import http
import pytest

from .common import MockPairingHandler, airplay_service, create_conf, mrp_service


@pytest.fixture(autouse=True, name="mock_scan")
def mock_scan_fixture():
    """Mock pyatv.scan."""
    with patch("homeassistant.components.apple_tv.config_flow.scan") as mock_scan:

        async def _scan(
            loop, timeout=5, identifier=None, protocol=None, hosts=None, aiozc=None
        ):
            if not mock_scan.hosts:
                mock_scan.hosts = hosts
            return mock_scan.result

        mock_scan.result = []
        mock_scan.hosts = None
        mock_scan.side_effect = _scan
        yield mock_scan


@pytest.fixture(name="dmap_pin")
def dmap_pin_fixture():
    """Mock pyatv.scan."""
    with patch("homeassistant.components.apple_tv.config_flow.randrange") as mock_pin:
        mock_pin.side_effect = lambda start, stop: 1111
        yield mock_pin


@pytest.fixture
def pairing():
    """Mock pyatv.scan."""
    with patch("homeassistant.components.apple_tv.config_flow.pair") as mock_pair:

        async def _pair(config, protocol, loop, session=None, **kwargs):
            handler = MockPairingHandler(
                await http.create_session(session), config.get_service(protocol)
            )
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

        async def _begin():
            pass

        async def _close():
            pass

        mock_pair.close.side_effect = _close
        mock_pair.begin.side_effect = _begin
        mock_pair.pin = lambda pin: None
        mock_pair.side_effect = _pair
        yield mock_pair


@pytest.fixture
def full_device(mock_scan, dmap_pin):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "MRP Device",
            mrp_service(),
            conf.ManualService(
                "dmapid",
                Protocol.DMAP,
                6666,
                {},
                pairing_requirement=PairingRequirement.Mandatory,
            ),
            airplay_service(),
        )
    )
    yield mock_scan


@pytest.fixture
def mrp_device(mock_scan):
    """Mock pyatv.scan."""
    mock_scan.result.extend(
        [
            create_conf(
                "127.0.0.1",
                "MRP Device",
                mrp_service(),
            ),
            create_conf(
                "127.0.0.2",
                "MRP Device 2",
                mrp_service(unique_id="unrelated"),
            ),
        ]
    )
    yield mock_scan


@pytest.fixture
def airplay_with_disabled_mrp(mock_scan):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "AirPlay Device",
            mrp_service(enabled=False),
            conf.ManualService(
                "airplayid",
                Protocol.AirPlay,
                7777,
                {},
                pairing_requirement=PairingRequirement.Mandatory,
            ),
        )
    )
    yield mock_scan


@pytest.fixture
def dmap_device(mock_scan):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "DMAP Device",
            conf.ManualService(
                "dmapid",
                Protocol.DMAP,
                6666,
                {},
                credentials=None,
                pairing_requirement=PairingRequirement.Mandatory,
            ),
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
            conf.ManualService(
                "dmapid",
                Protocol.DMAP,
                6666,
                {},
                credentials="dummy_creds",
                pairing_requirement=PairingRequirement.NotNeeded,
            ),
        )
    )
    yield mock_scan


@pytest.fixture
def airplay_device_with_password(mock_scan):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "AirPlay Device",
            conf.ManualService(
                "airplayid", Protocol.AirPlay, 7777, {}, requires_password=True
            ),
        )
    )
    yield mock_scan


@pytest.fixture
def dmap_with_requirement(mock_scan, pairing_requirement):
    """Mock pyatv.scan."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "DMAP Device",
            conf.ManualService(
                "dmapid",
                Protocol.DMAP,
                6666,
                {},
                pairing_requirement=pairing_requirement,
            ),
        )
    )
    yield mock_scan
