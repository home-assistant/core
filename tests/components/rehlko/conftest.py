"""Module for testing the Rehlko integration in Home Assistant."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.rehlko import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_value_fixture

TEST_EMAIL = "MyEmail@email.com"
TEST_PASSWORD = "password"
TEST_SUBJECT = TEST_EMAIL.lower()
TEST_REFRESH_TOKEN = "my_refresh_token"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rehlko.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="homes")
def rehlko_homes_fixture() -> list[dict[str, Any]]:
    """Create sonos favorites fixture."""
    return load_json_value_fixture("homes.json", DOMAIN)


@pytest.fixture(name="generator")
def rehlko_generator_fixture() -> dict[str, Any]:
    """Create sonos favorites fixture."""
    return load_json_value_fixture("generator.json", DOMAIN)


@pytest.fixture(name="rehlko_config_entry")
def rehlko_config_entry_fixture() -> MockConfigEntry:
    """Create a config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        unique_id=TEST_SUBJECT,
    )


@pytest.fixture(name="rehlko_config_entry_with_refresh_token")
def rehlko_config_entry_with_refresh_token_fixture() -> MockConfigEntry:
    """Create a config entry fixture with refresh token."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_REFRESH_TOKEN: TEST_REFRESH_TOKEN,
        },
        unique_id=TEST_SUBJECT,
    )


@pytest.fixture
async def mock_rehlko(
    homes: list[dict[str, Any]],
    generator: dict[str, Any],
):
    """Mock Rehlko instance."""
    with (
        patch("homeassistant.components.rehlko.AioKem", autospec=True) as mock_kem,
        patch("homeassistant.components.rehlko.config_flow.AioKem", new=mock_kem),
    ):
        client = mock_kem.return_value
        client.get_homes = AsyncMock(return_value=homes)
        client.get_generator_data = AsyncMock(return_value=generator)
        client.authenticate = AsyncMock(return_value=None)
        client.get_token_subject = Mock(return_value=TEST_SUBJECT)
        client.get_refresh_token = AsyncMock(return_value=TEST_REFRESH_TOKEN)
        client.set_refresh_token_callback = Mock()
        client.set_retry_policy = Mock()
        yield client


@pytest.fixture
async def load_rehlko_config_entry(
    hass: HomeAssistant,
    mock_rehlko: Mock,
    rehlko_config_entry: MockConfigEntry,
) -> None:
    """Load the config entry."""
    rehlko_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(rehlko_config_entry.entry_id)
    await hass.async_block_till_done()
