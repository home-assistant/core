"""Fixtures for component."""

from collections.abc import Generator
from dataclasses import dataclass
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pyatv.const import DeviceState, FeatureName, FeatureState, PowerState
from pyatv.interface import Playing
import pytest

from homeassistant.components.apple_tv.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

if sys.version_info < (3, 14):
    from pyatv import conf
    from pyatv.const import PairingRequirement, Protocol
    from pyatv.support import http

    from .common import MockPairingHandler, airplay_service, create_conf, mrp_service

if sys.version_info >= (3, 14):
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(autouse=True, name="mock_scan")
def mock_scan_fixture() -> Generator[AsyncMock]:
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
def dmap_pin_fixture() -> Generator[MagicMock]:
    """Mock pyatv.scan."""
    with patch("homeassistant.components.apple_tv.config_flow.randrange") as mock_pin:
        mock_pin.side_effect = lambda start, stop: 1111
        yield mock_pin


@pytest.fixture
def pairing() -> Generator[AsyncMock]:
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
def pairing_mock() -> Generator[AsyncMock]:
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
def full_device(mock_scan: AsyncMock, dmap_pin: MagicMock) -> AsyncMock:
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
    return mock_scan


@pytest.fixture
def mrp_device(mock_scan: AsyncMock) -> AsyncMock:
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
    return mock_scan


@pytest.fixture
def airplay_with_disabled_mrp(mock_scan: AsyncMock) -> AsyncMock:
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
    return mock_scan


@pytest.fixture
def dmap_device(mock_scan: AsyncMock) -> AsyncMock:
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
    return mock_scan


@pytest.fixture
def dmap_device_with_credentials(mock_scan: AsyncMock) -> AsyncMock:
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
    return mock_scan


@pytest.fixture
def airplay_device_with_password(mock_scan: AsyncMock) -> AsyncMock:
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
    return mock_scan


@pytest.fixture
def dmap_with_requirement(
    mock_scan: AsyncMock, pairing_requirement: PairingRequirement
) -> AsyncMock:
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
    return mock_scan


@dataclass
class FakeFeatures:
    """Simulate pyatv.features with in_state method."""

    power_feature_available: bool = True

    def in_state(self, state: FeatureState, feature: FeatureName) -> bool:
        """Always return Available except for PowerState if specified."""
        if feature is FeatureName.PowerState and state is FeatureState.Available:
            return self.power_feature_available
        return True

    def all_features(self) -> dict[FeatureName, SimpleNamespace]:
        """Return all features."""
        return {f: SimpleNamespace(state=FeatureState.Available) for f in FeatureName}


@dataclass
class DummyPower:
    """Simulate pyatv.power with listener callbacks and async on/off."""

    def __init__(self) -> None:
        """Initialize power state and listener."""
        self.listener = None
        self.power_state = PowerState.On

    async def _notify(self, old: PowerState, new: PowerState) -> None:
        """Notify all listeners asynchronously."""
        if self.listener and hasattr(self.listener, "powerstate_update"):
            self.listener.powerstate_update(old, new)

    async def turn_off(self) -> None:
        """Simulate turning off the device."""
        old = self.power_state
        self.power_state = PowerState.Off
        await self._notify(old, self.power_state)

    async def turn_on(self) -> None:
        """Simulate turning on the device."""
        old = self.power_state
        self.power_state = PowerState.On
        await self._notify(old, self.power_state)


@dataclass
class DummyPushUpdater:
    """Simulate pyatv.push_updater with listener behavior."""

    def __init__(self) -> None:
        """Initialize push updater state and listener."""
        self.listener = None
        self.is_active = True
        self.playing_state = Playing(device_state=DeviceState.Paused)

    def start(self) -> None:
        """Start the push updater."""
        self.is_active = True

    def stop(self) -> None:
        """Stop the push updater."""
        self.is_active = False

    async def trigger_playing(self, new_state: DeviceState) -> None:
        """Simulate a playstatus update event."""
        self.playing_state = Playing(device_state=new_state)
        if (
            self.is_active
            and self.listener
            and hasattr(self.listener, "playstatus_update")
        ):
            self.listener.playstatus_update(self, self.playing_state)


@pytest.fixture
def dummy_atv_runtime() -> AsyncMock:
    """Unified dummy Apple TV device mock with runtime listener-capable subsystems."""
    atv = AsyncMock()
    atv.power = DummyPower()
    atv.features = FakeFeatures()
    atv.push_updater = DummyPushUpdater()

    async def play():
        await atv.push_updater.trigger_playing(DeviceState.Playing)

    atv.remote_control.play = AsyncMock(side_effect=play)
    atv.close = lambda: None
    return atv


@pytest.fixture
async def setup_runtime_integration_power_tests(
    hass: HomeAssistant, dummy_atv_runtime, request: pytest.FixtureRequest
) -> tuple[MockConfigEntry, AsyncMock]:
    """Set up Apple TV integration using runtime dummy (for media_player tests)."""

    power_feature_available = getattr(request, "param", True)
    # Modify dummy to simulate missing PowerState feature
    dummy_atv_runtime.features.power_feature_available = power_feature_available

    async def _fake_setup_component(
        hass: HomeAssistant, domain: str, config: dict
    ) -> bool:
        """Intercept setup_component calls."""
        if domain == "zeroconf":
            return True
        return await async_setup_component(hass, domain, config)

    async def _fake_connect_once(self, raise_missing_credentials=True):
        """Simulate Apple TV connecting successfully."""
        atv = dummy_atv_runtime
        self.atv = atv
        return True

    with (
        patch(
            "homeassistant.components.apple_tv.AppleTVManager._connect_once",
            new=_fake_connect_once,
        ),
        patch(
            "homeassistant.setup.async_setup_component",
            side_effect=_fake_setup_component,
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Dummy TV",
            data={
                "address": "127.0.0.1",
                "host": "127.0.0.1",
                "identifier": "dummyid",
                "name": "Dummy TV",
                "credentials": {"3": "abc123", "1": "xyz789"},
            },
            unique_id="dummyid_runtime"
            + ("_nopower" if not power_feature_available else ""),
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry, dummy_atv_runtime
