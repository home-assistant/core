"""Fixtures for component."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyatv import conf
from pyatv.const import (
    DeviceModel,
    FeatureName,
    FeatureState,
    KeyboardFocusState,
    PairingRequirement,
    Protocol,
)
from pyatv.interface import FeatureInfo, Features, Playing, PushUpdater
from pyatv.support import http
import pytest

from homeassistant.components.apple_tv.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from .common import MockPairingHandler, airplay_service, create_conf, mrp_service

from tests.common import MockConfigEntry


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


class _MockFeatures(Features):
    """Real Features implementation with configurable per-feature state."""

    def __init__(self, default: FeatureState = FeatureState.Available) -> None:
        """Initialize with a default state applied to every feature."""
        self._default = default
        self._overrides: dict[FeatureName, FeatureState] = {}

    def set_state(self, feature: FeatureName, state: FeatureState) -> None:
        """Override the reported state for a single feature."""
        self._overrides[feature] = state

    def get_feature(self, feature_name: FeatureName) -> FeatureInfo:
        """Return the (possibly overridden) state for a feature."""
        return FeatureInfo(state=self._overrides.get(feature_name, self._default))


class _MockPushUpdater(PushUpdater):
    """Real PushUpdater with the I/O replaced by an in-memory delivery."""

    def __init__(self, playing: Playing) -> None:
        """Store the play status that will be delivered on start()."""
        super().__init__()
        self._playing = playing
        self._active = False

    @property
    def active(self) -> bool:
        """Return whether the updater is active."""
        return self._active

    def start(self, initial_delay: int = 0) -> None:
        """Synchronously deliver the canned play status to the listener."""
        self._active = True
        self.listener.playstatus_update(self, self._playing)

    def stop(self) -> None:
        """Stop forwarding updates."""
        self._active = False


@pytest.fixture
def mock_atv() -> AsyncMock:
    """Create a mock Apple TV interface."""
    atv = AsyncMock()
    atv.close = MagicMock()
    atv.features = _MockFeatures()
    atv.keyboard = AsyncMock()
    atv.push_updater = _MockPushUpdater(Playing())
    atv.stream = AsyncMock()
    atv.keyboard.text_focus_state = KeyboardFocusState.Focused
    atv.device_info.model = DeviceModel.Gen4K
    atv.device_info.raw_model = "AppleTV6,2"
    atv.device_info.version = "15.0"
    atv.device_info.mac = "AA:BB:CC:DD:EE:FF"
    return atv


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create an Apple TV mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        unique_id="mrpid",
        data={
            CONF_ADDRESS: "127.0.0.1",
            CONF_NAME: "Living Room",
            "credentials": {str(Protocol.MRP.value): "mrp_creds"},
            "identifiers": ["mrpid"],
        },
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
    mock_atv: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up Apple TV integration with mocked pyatv."""
    mock_config_entry.add_to_hass(hass)

    scan_result = create_conf("127.0.0.1", "Living Room", mrp_service())

    with (
        patch("homeassistant.components.apple_tv.scan", return_value=[scan_result]),
        patch("homeassistant.components.apple_tv.connect", return_value=mock_atv),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


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
