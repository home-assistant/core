"""Configuration for frontier_silicon tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from afsapi import Equaliser, FSConnectionError, PlayCaps, PlayerMode, Preset
from afsapi.nodes import PresetsListItem
import pytest

from homeassistant.components.frontier_silicon.const import CONF_WEBFSAPI_URL, DOMAIN
from homeassistant.const import CONF_PIN

from tests.common import MockConfigEntry


class FakeAFSAPIDevice:
    """A fake Frontier Silicon Device."""

    # registry of fake AFSAPI devices
    afsapi_device_map = {}

    def __new__(cls, webfsapi_endpoint: str, pin: str | int, timeout: int = 2):
        """Create or reuse a fake device for the endpoint."""

        if webfsapi_endpoint not in cls.afsapi_device_map:
            cls.afsapi_device_map[webfsapi_endpoint] = super().__new__(cls)
        return cls.afsapi_device_map[webfsapi_endpoint]

    def __init__(
        self, webfsapi_endpoint: str, pin: str | int, timeout: int = 2
    ) -> None:
        """Constructor."""
        if not hasattr(self, "init_done"):
            self.webfsapi_endpoint = webfsapi_endpoint
            self.reset()
            self.init_done = True

    def reset(self):
        """Reset the state of the device, ready for the next test."""
        self.fail_get_power = False
        self.has_power = False

    async def get_radio_id(self) -> str:
        """Mock get_radio_id AFSAPI function."""
        return "FakeID"

    async def get_power(self) -> bool:
        """Mock get_power AFSAPI function."""
        if self.fail_get_power:
            raise FSConnectionError
        return self.has_power

    async def get_play_name(self) -> str:
        """Mock get_play_name AFSAPI function."""
        return "Something Playing"

    async def get_play_text(self) -> str:
        """Mock get_play_text AFSAPI function."""
        return "Something Playing Extra Text"

    async def get_play_artist(self) -> str:
        """Mock get_play_artist AFSAPI function."""
        return "Artist Name"

    async def get_play_album(self) -> str:
        """Mock get_play_album AFSAPI function."""
        return "Album Name"

    async def get_play_status(self) -> int:
        """Mock get_play_status AFSAPI function."""
        return 0

    async def get_mode(self) -> PlayerMode:
        """Mock get_mode AFSAPI function."""
        available_modes = await self.get_modes()
        return available_modes[0]

    async def get_mute(self) -> bool:
        """Mock get_mute AFSAPI function."""
        return False

    async def get_volume(self) -> int:
        """Mock get_volume AFSAPI function."""
        return 3

    async def get_play_graphic(self) -> str:
        """Mock get_play_graphic AFSAPI function."""
        return "https://1.1.1.1/graphic_url"

    async def get_modes(self) -> list[PlayerMode]:
        """Mock get_modes AFSAPI function."""
        valid_modes = [(0, {"id": "mocked_mode0", "label": "MockedMode"})]

        return [
            PlayerMode(
                id=v["id"],
                key=int(k),
                label=v.get("label"),
                selectable=v.get("selectable"),
                streamable=v.get("streamable"),
                modetype=v.get("modeType"),
            )
            for k, v in valid_modes
        ]

    async def get_play_caps(self) -> PlayCaps | None:
        """Mock get_play_caps AFSAPI function."""
        return PlayCaps(0)

    async def get_presets(self) -> list[Preset]:
        """Mock get_presets AFSAPI function."""

        def _to_preset(
            key: str,
            preset_fields: PresetsListItem,
        ) -> Preset:
            """Internal helper function to convert data to Preset."""
            return Preset(int(key), preset_fields.get("type"), preset_fields["name"])

        presets_data = [(0, {"type": "mocked_eqpreset_type0", "name": "MockedPreset"})]

        return [_to_preset(key, preset_fields) for key, preset_fields in presets_data]

    async def get_eq_preset(self) -> Equaliser:
        """Mock get_eq_preset AFSAPI function."""
        available_equalisers = await self.get_equalisers()
        return available_equalisers[0]

    async def get_equalisers(self) -> list[Equaliser]:
        """Mock get_equalisers AFSAPI function."""
        equalisers_data = [(0, {"label": "MockedEq"})]
        return [
            Equaliser(key=int(key), label=eqinfo["label"])
            for key, eqinfo in equalisers_data
        ]

    async def get_volume_steps(self) -> int:
        """Mock get_volume_steps AFSAPI function."""
        return 2


@pytest.fixture
def fake_afsapi_dev(config_entry: MockConfigEntry):
    """Return a test FakeAFSAPIDevice, creating it for an endpoint if needed."""
    webfsapi_endpoint = config_entry.data[CONF_WEBFSAPI_URL]
    pin = config_entry.data[CONF_PIN]
    fake_dev = FakeAFSAPIDevice(webfsapi_endpoint, pin)
    yield fake_dev
    fake_dev.reset()


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock Frontier Silicon config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="mock_radio_id",
        data={CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi", CONF_PIN: "1234"},
    )


@pytest.fixture(autouse=True)
def mock_valid_device_url() -> Generator[None]:
    """Return a valid webfsapi endpoint."""
    with patch(
        "afsapi.AFSAPI.get_webfsapi_endpoint",
        return_value="http://1.1.1.1:80/webfsapi",
    ):
        yield


@pytest.fixture(autouse=True)
def mock_valid_pin() -> Generator[None]:
    """Make get_friendly_name return a value, indicating a valid pin."""
    with patch(
        "afsapi.AFSAPI.get_friendly_name",
        return_value="Name of the device",
    ):
        yield


@pytest.fixture(autouse=True)
def mock_radio_id() -> Generator[None]:
    """Return a valid radio_id."""
    with patch("afsapi.AFSAPI.get_radio_id", return_value="mock_radio_id"):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.frontier_silicon.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
