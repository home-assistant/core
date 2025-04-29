"""Module for testing the KEM integration in Home Assistant."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.kem.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_value_fixture

TEST_EMAIL = "MyEmail@email.com"
TEST_PASSWORD = "password"
TEST_SUBJECT = TEST_EMAIL.lower()
TEST_REFRESH_TOKEN = "my_refresh_token"


@pytest.fixture(name="homes")
def kem_homes_fixture() -> list[dict[str, Any]]:
    """Create sonos favorites fixture."""
    return load_json_value_fixture("homes.json", DOMAIN)


@pytest.fixture(name="generator")
def kem_generator_fixture() -> dict[str, Any]:
    """Create sonos favorites fixture."""
    return load_json_value_fixture("generator.json", DOMAIN)


@pytest.fixture(name="kem_config_entry")
def kem_config_entry_fixture() -> MockConfigEntry:
    """Create a config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        unique_id=TEST_SUBJECT,
    )


@pytest.fixture(name="kem_config_entry_with_refresh_token")
def kem_config_entry_with_refresh_token_fixture() -> MockConfigEntry:
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


@pytest.fixture(name="mock_kem")
async def mock_kem(
    homes: list[dict[str, Any]],
    generator: dict[str, Any],
):
    """Mock KEM instance."""
    with (
        patch("homeassistant.components.kem.AioKem") as mock_kem,
        patch("homeassistant.components.kem.config_flow.AioKem") as mock_cf_kem,
    ):
        mock_instance = AsyncMock()
        mock_kem.return_value = mock_instance
        mock_cf_kem.return_value = mock_instance
        mock_instance.get_homes = AsyncMock(return_value=homes)
        mock_instance.get_generator_data = AsyncMock(return_value=generator)
        mock_instance.authenticate = AsyncMock(return_value=None)
        mock_instance.get_token_subject = Mock(return_value=TEST_SUBJECT)
        mock_instance.get_refresh_token = AsyncMock(return_value=TEST_REFRESH_TOKEN)
        mock_instance.set_refresh_token_callback = Mock()
        mock_instance.set_retry_policy = Mock()
        yield mock_instance


@pytest.fixture(name="load_kem_config_entry")
async def load_kem_config_entry(
    hass: HomeAssistant,
    mock_kem: Mock,
    kem_config_entry: MockConfigEntry,
) -> None:
    """Load the config entry."""
    kem_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(kem_config_entry.entry_id)
    await hass.async_block_till_done()
