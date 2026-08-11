"""Configuration for frontier_silicon tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from afsapi import Equaliser, PlayCaps, PlayerMode, Preset
from afsapi.nodes import PresetsListItem
import pytest

from homeassistant.components.frontier_silicon.const import CONF_WEBFSAPI_URL, DOMAIN
from homeassistant.const import CONF_PIN

from tests.common import MockConfigEntry


class FakeAFSAPIDevice:
    """A fake Frontier Silicon Device."""

    def __init__(
        self, webfsapi_endpoint: str, pin: str | int, timeout: int = 2
    ) -> None:
        """Constructor."""

    async def get_radio_id(self) -> str:
        """Mock get_radio_id AFSAPI function."""
        return "FakeID"

    async def get_power(self) -> bool:
        """Mock get_power AFSAPI function."""
        return False

    async def get_play_status(self) -> int:
        """Mock get_play_status AFSAPI function."""
        return 0

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

        presets_data = [(0, {"id": "mocked_eqpreset0", "label": "MockedPreset"})]

        return [_to_preset(key, preset_fields) for key, preset_fields in presets_data]

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
