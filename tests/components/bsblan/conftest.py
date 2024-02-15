"""Fixtures for BSBLAN integration tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bsblan import Device, Info, State
import pytest

from homeassistant.components.bsblan.const import CONF_PASSKEY, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="BSBLAN Setup",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id="00:80:41:19:69:90",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.bsblan.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_bsblan(request: pytest.FixtureRequest) -> Generator[None, MagicMock, None]:
    """Return a mocked BSBLAN client."""

    with patch(
        "homeassistant.components.bsblan.BSBLAN", autospec=True
    ) as bsblan_mock, patch(
        "homeassistant.components.bsblan.config_flow.BSBLAN", new=bsblan_mock
    ):
        bsblan = bsblan_mock.return_value
        bsblan.info.return_value = Info.parse_raw(load_fixture("info.json", DOMAIN))
        bsblan.device.return_value = Device.parse_raw(
            load_fixture("device.json", DOMAIN)
        )
        bsblan.state.return_value = State.parse_raw(load_fixture("state.json", DOMAIN))
        yield bsblan


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_bsblan: MagicMock
) -> MockConfigEntry:
    """Set up the bsblan integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
