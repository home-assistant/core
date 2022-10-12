"""Fixtures for Elgato integration tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from elgato import Info, Settings, State
import pytest

from homeassistant.components.elgato.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="CN11A1A00001",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PORT: 9123,
        },
        unique_id="CN11A1A00001",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.elgato.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_onboarding() -> Generator[None, MagicMock, None]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        yield mock_onboarding


@pytest.fixture
def mock_elgato_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked Elgato client."""
    with patch(
        "homeassistant.components.elgato.config_flow.Elgato", autospec=True
    ) as elgato_mock:
        elgato = elgato_mock.return_value
        elgato.info.return_value = Info.parse_raw(load_fixture("info.json", DOMAIN))
        yield elgato


@pytest.fixture
def mock_elgato(request: pytest.FixtureRequest) -> Generator[None, MagicMock, None]:
    """Return a mocked Elgato client."""
    variant = {"state": "temperature", "settings": "temperature"}
    if hasattr(request, "param") and request.param:
        variant = request.param

    with patch("homeassistant.components.elgato.Elgato", autospec=True) as elgato_mock:
        elgato = elgato_mock.return_value
        elgato.info.return_value = Info.parse_raw(load_fixture("info.json", DOMAIN))
        elgato.state.return_value = State.parse_raw(
            load_fixture(f"state-{variant['state']}.json", DOMAIN)
        )
        elgato.settings.return_value = Settings.parse_raw(
            load_fixture(f"settings-{variant['settings']}.json", DOMAIN)
        )
        yield elgato


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_elgato: MagicMock
) -> MockConfigEntry:
    """Set up the Elgato integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
