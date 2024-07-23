"""Fixtures for Elgato integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from elgato import BatteryInfo, ElgatoNoBatteryError, Info, Settings, State
import pytest

from homeassistant.components.elgato.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, get_fixture_path, load_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture
def device_fixtures() -> str:
    """Return the device fixtures for a specific device."""
    return "key-light"


@pytest.fixture
def state_variant() -> str:
    """Return the state variant to load for a device."""
    return "state"


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
def mock_elgato(
    device_fixtures: str, state_variant: str
) -> Generator[None, MagicMock, None]:
    """Return a mocked Elgato client."""
    with (
        patch(
            "homeassistant.components.elgato.coordinator.Elgato", autospec=True
        ) as elgato_mock,
        patch("homeassistant.components.elgato.config_flow.Elgato", new=elgato_mock),
    ):
        elgato = elgato_mock.return_value
        elgato.info.return_value = Info.from_json(
            load_fixture(f"{device_fixtures}/info.json", DOMAIN)
        )
        elgato.state.return_value = State.from_json(
            load_fixture(f"{device_fixtures}/{state_variant}.json", DOMAIN)
        )
        elgato.settings.return_value = Settings.from_json(
            load_fixture(f"{device_fixtures}/settings.json", DOMAIN)
        )

        # This may, or may not, be a battery-powered device
        if get_fixture_path(f"{device_fixtures}/battery.json", DOMAIN).exists():
            elgato.has_battery.return_value = True
            elgato.battery.return_value = BatteryInfo.from_json(
                load_fixture(f"{device_fixtures}/battery.json", DOMAIN)
            )
        else:
            elgato.has_battery.return_value = False
            elgato.battery.side_effect = ElgatoNoBatteryError

        yield elgato


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_elgato: MagicMock,
) -> MockConfigEntry:
    """Set up the Elgato integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
