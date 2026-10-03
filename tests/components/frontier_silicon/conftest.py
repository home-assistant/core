"""Configuration for frontier_silicon tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from afsapi import Equaliser, PlayCaps, PlayerMode, PlayState, Preset
import pytest

from homeassistant.components.frontier_silicon.const import CONF_WEBFSAPI_URL, DOMAIN
from homeassistant.const import CONF_PIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.frontier_silicon.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_afsapi() -> Generator[AsyncMock]:
    """Mock a Frontier Silicon AFSAPI client."""
    with (
        patch(
            "homeassistant.components.frontier_silicon.AFSAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.frontier_silicon.config_flow.AFSAPI",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.webfsapi_endpoint = "http://1.1.1.1:80/webfsapi"

        # get_webfsapi_endpoint is a staticmethod on the class; expose it on the
        # instance mock too so tests can configure it via the yielded client.
        mock_client.get_webfsapi_endpoint.return_value = "http://1.1.1.1:80/webfsapi"
        client.get_webfsapi_endpoint = mock_client.get_webfsapi_endpoint
        client.get_friendly_name.return_value = "Name of the device"
        client.get_radio_id.return_value = "mock_radio_id"

        client.get_power.return_value = False
        client.get_play_status.return_value = PlayState.IDLE
        client.get_play_name.return_value = "Something Playing"
        client.get_play_text.return_value = "Something Playing Extra Text"
        client.get_play_artist.return_value = "Artist Name"
        client.get_play_album.return_value = "Album Name"
        client.get_play_graphic.return_value = "https://1.1.1.1/graphic_url"
        client.get_mute.return_value = False
        client.get_volume.return_value = 3
        client.get_volume_steps.return_value = 2
        client.get_play_caps.return_value = PlayCaps(0)
        client.get_dst.return_value = True
        client.set_dst.return_value = True

        modes = [
            PlayerMode(
                id="mocked_mode0",
                key=0,
                label="MockedMode",
                selectable=True,
                streamable=None,
                modetype=None,
            )
        ]
        client.get_modes.return_value = modes
        client.get_mode.return_value = modes[0]

        equalisers = [Equaliser(key=0, label="MockedEq")]
        client.get_equalisers.return_value = equalisers
        client.get_eq_preset.return_value = equalisers[0]

        client.get_presets.return_value = [
            Preset(0, "mocked_eqpreset_type0", "MockedPreset")
        ]

        yield client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock Frontier Silicon config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Name of the device",
        unique_id="mock_radio_id",
        data={CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi", CONF_PIN: "1234"},
    )
