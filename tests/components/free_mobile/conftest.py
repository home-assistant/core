"""Test fixtures for Free Mobile."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_USERNAME = "12345678"
TEST_ACCESS_TOKEN = "test_token_123"
CONF_INPUT = {CONF_USERNAME: TEST_USERNAME, CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN}


@pytest.fixture
def mock_freesms() -> Generator[AsyncMock]:
    """Mock the freesms library."""
    mock_instance = MagicMock()
    mock_instance.send_sms.return_value.status_code = 200
    mock_instance.send_sms.return_value.ok = True

    with (
        patch(
            "homeassistant.components.free_mobile.config_flow.FreeClient",
            return_value=mock_instance,
        ),
        patch(
            "homeassistant.components.free_mobile.FreeClient",
            return_value=mock_instance,
        ),
        patch(
            "homeassistant.components.free_mobile.notify.FreeClient",
            return_value=mock_instance,
        ),
    ):
        yield mock_instance


@pytest.fixture
def mock_freesms_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Fixture to create a mocked ConfigEntry."""
    return MockConfigEntry(
        title=TEST_USERNAME,
        domain=DOMAIN,
        data=CONF_INPUT,
    )


@pytest.fixture
async def configure_free_mobile_through_yaml(
    hass: HomeAssistant, mock_freesms: AsyncMock
) -> None:
    """Configure the notify domain with YAML for the Free Mobile platform."""
    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    CONF_USERNAME: TEST_USERNAME,
                    CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
                },
            ]
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
async def free_mobile_notification_entity(
    hass: HomeAssistant,
    mock_freesms: AsyncMock,
    mock_freesms_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Configure a Free Mobile Notification Entity."""
    mock_freesms_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_freesms_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_freesms_config_entry
