"""Test fixtures for the Sony TV RS-232 integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sony_tv_rs232.const import DOMAIN
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant

from . import MOCK_PORT, default_state


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sony_tv_rs232.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_sony_tv() -> Generator[MagicMock]:
    """Mock a Sony TV that is on and answers queries (a Pro Bravia does).

    The query mocks answer from ``state`` so a poll sees whatever the test put
    there.
    """
    with (
        patch(
            "homeassistant.components.sony_tv_rs232.SonyTV", autospec=True
        ) as mock_tv,
        patch(
            "homeassistant.components.sony_tv_rs232.config_flow.SonyTV",
            new=mock_tv,
        ),
    ):
        tv = mock_tv.return_value
        tv.state = default_state()
        tv.connected = True
        tv.supports_queries = True
        tv.query_power.side_effect = lambda: tv.state.power
        tv.query_input_source.side_effect = lambda: tv.state.input_source
        tv.query_volume.side_effect = lambda: tv.state.volume
        tv.query_mute.side_effect = lambda: tv.state.audio_mute
        tv.query_sound_mode.side_effect = lambda: tv.state.sound_mode

        yield tv


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: MOCK_PORT},
        title="Sony TV",
        entry_id="01KPBBPM6WCQ8148EFR0TCG1WW",
    )


@pytest.fixture(autouse=True)
async def mock_usb_component(hass: HomeAssistant) -> None:
    """Mock the USB component to prevent setup failures."""
    hass.config.components.add("usb")
