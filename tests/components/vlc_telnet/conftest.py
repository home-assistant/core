"""Fixtures for vlc_telnet tests."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, create_autospec, patch

from aiovlc.client import Client
import pytest

from homeassistant.components.vlc_telnet.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 4212,
    CONF_PASSWORD: "test-password",
}


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def vlc_mock() -> MagicMock:
    """Return a mocked VLC client."""
    mock = create_autospec(Client, instance=True)
    status_result = MagicMock()
    status_result.audio_volume = 100
    status_result.state = "idle"
    mock.status.return_value = status_result
    mock.get_length.return_value = MagicMock(length=0)
    mock.get_time.return_value = MagicMock(time=0)
    mock.info.return_value = MagicMock(data={})
    return mock


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    vlc_mock: MagicMock,
) -> AsyncGenerator[None]:
    """Set up the VLC integration."""
    with patch(
        "homeassistant.components.vlc_telnet.Client",
        return_value=vlc_mock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield
