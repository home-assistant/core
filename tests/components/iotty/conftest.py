"""Fixtures for iotty integration tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import setup
from homeassistant.components.iotty import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry

CLIENT_ID = "client_id"
CLIENT_SECRET = "client_secret"
REDIRECT_URI = "https://example.com/auth/external/callback"


@pytest.fixture
async def local_impl(hass: HomeAssistant):
    """Local implementation."""
    assert await setup.async_setup_component(hass, "auth", {})
    return config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass, DOMAIN, "client_id", "client_secret", "authorize_url", "token_url"
    )


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="IOTTY00001",
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            CONF_HOST: "127.0.0.1",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PORT: 9123,
        },
        unique_id="IOTTY00001",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.iotty.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


# @pytest.fixture
# async def init_integration(
#     hass: HomeAssistant,
#     mock_config_entry: MockConfigEntry,
#     mock_iotty: MagicMock,
# ) -> MockConfigEntry:
#     """Set up the integration for testing."""
#     mock_config_entry.add_to_hass(hass)

#     await hass.config_entries.async_setup(mock_config_entry.entry_id)
#     await hass.async_block_till_done()

#     return mock_config_entry


@pytest.fixture
def mock_iotty(
    # device_fixtures: str, state_variant: str
) -> Generator[None, MagicMock, None]:
    """Return a mocked iotty Apilient."""
    # with patch(
    #     "homeassistant.components.elgato.coordinator.Elgato", autospec=True
    # ) as elgato_mock, patch(
    #     "homeassistant.components.elgato.config_flow.Elgato", new=elgato_mock
    # ):
    #     elgato = elgato_mock.return_value
    #     elgato.info.return_value = Info.parse_raw(
    #         load_fixture(f"{device_fixtures}/info.json", DOMAIN)
    #     )
    #     elgato.state.return_value = State.parse_raw(
    #         load_fixture(f"{device_fixtures}/{state_variant}.json", DOMAIN)
    #     )
    #     elgato.settings.return_value = Settings.parse_raw(
    #         load_fixture(f"{device_fixtures}/settings.json", DOMAIN)
    #     )

    #     # This may, or may not, be a battery-powered device
    #     if get_fixture_path(f"{device_fixtures}/battery.json", DOMAIN).exists():
    #         elgato.has_battery.return_value = True
    #         elgato.battery.return_value = BatteryInfo.parse_raw(
    #             load_fixture(f"{device_fixtures}/battery.json", DOMAIN)
    #         )
    #     else:
    #         elgato.has_battery.return_value = False
    #         elgato.battery.side_effect = ElgatoNoBatteryError

    #     yield elgato
