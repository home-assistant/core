"""Test fixtures for Prowl."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_NAME = "TestProwl"
TEST_SERVICE = TEST_NAME.lower()
ENTITY_ID = f"{NOTIFY_DOMAIN}.{TEST_SERVICE}"
TEST_API_KEY = "f00f" * 10
OTHER_API_KEY = "beef" * 10
CONF_INPUT = {CONF_API_KEY: TEST_API_KEY, CONF_NAME: TEST_NAME}
CONF_INPUT_NEW_KEY = {CONF_API_KEY: OTHER_API_KEY}
INVALID_API_KEY_ERROR = {"base": "invalid_api_key"}
TIMEOUT_ERROR = {"base": "api_timeout"}
BAD_API_RESPONSE = {"base": "bad_api_response"}


@pytest.fixture
async def configure_prowl_through_yaml(
    hass: HomeAssistant, mock_prowlpy: Generator[AsyncMock]
) -> Generator[None]:
    """Configure the notify domain with YAML for the Prowl platform."""
    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {
                    "name": TEST_NAME,
                    "platform": DOMAIN,
                    "api_key": TEST_API_KEY,
                },
            ]
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
async def prowl_notification_entity(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    mock_prowlpy_config_entry: MockConfigEntry,
) -> Generator[MockConfigEntry]:
    """Configure a Prowl Notification Entity."""
    mock_prowlpy.verify_key.return_value = True

    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_prowlpy_config_entry


@pytest.fixture
def mock_prowlpy() -> Generator[AsyncMock]:
    """Mock the prowlpy library."""
    mock_instance = AsyncMock()

    with (
        patch(
            "homeassistant.components.prowl.notify.prowlpy.AsyncProwl",
            return_value=mock_instance,
        ),
        patch(
            "homeassistant.components.prowl.helpers.prowlpy.AsyncProwl",
            return_value=mock_instance,
        ),
        patch(
            "homeassistant.components.prowl.__init__.prowlpy.AsyncProwl",
            return_value=mock_instance,
        ),
    ):
        yield mock_instance


@pytest.fixture
async def mock_prowlpy_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Fixture to create a mocked ConfigEntry."""
    return MockConfigEntry(
        title=TEST_NAME, domain=DOMAIN, data={CONF_API_KEY: TEST_API_KEY}
    )
