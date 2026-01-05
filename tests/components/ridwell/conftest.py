"""Define test fixtures for Ridwell."""

from collections.abc import Generator
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aioridwell.model import EventState, RidwellPickup, RidwellPickupEvent
import pytest

from homeassistant.components.ridwell.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_ACCOUNT_ID = "12345"
TEST_DASHBOARD_URL = "https://www.ridwell.com/users/12345/dashboard"
TEST_PASSWORD = "password"
TEST_USERNAME = "user@email.com"
TEST_USER_ID = "12345"


@pytest.fixture(name="account")
def account_fixture() -> Mock:
    """Define a Ridwell account."""
    return Mock(
        account_id=TEST_ACCOUNT_ID,
        address={
            "street1": "123 Main Street",
            "city": "New York",
            "state": "New York",
            "postal_code": "10001",
        },
        async_get_pickup_events=AsyncMock(
            return_value=[
                RidwellPickupEvent(
                    None,
                    "event_123",
                    date(2022, 1, 24),
                    [RidwellPickup("Plastic Film", "offer_123", 1, "product_123", 1)],
                    EventState.INITIALIZED,
                )
            ]
        ),
    )


@pytest.fixture(name="client")
def client_fixture(account: Mock) -> Mock:
    """Define an aioridwell client."""
    return Mock(
        async_authenticate=AsyncMock(),
        async_get_accounts=AsyncMock(return_value={TEST_ACCOUNT_ID: account}),
        get_dashboard_url=Mock(return_value=TEST_DASHBOARD_URL),
        user_id=TEST_USER_ID,
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant, config: dict[str, Any]
) -> MockConfigEntry:
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=config[CONF_USERNAME],
        data=config,
        entry_id="11554ec901379b9cc8f5a6c1d11ce978",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }


@pytest.fixture(name="mock_aioridwell")
def mock_aioridwell_fixture(client: Mock, config: dict[str, Any]) -> Generator[None]:
    """Define a fixture to patch aioridwell."""
    with (
        patch(
            "homeassistant.components.ridwell.config_flow.async_get_client",
            return_value=client,
        ),
        patch(
            "homeassistant.components.ridwell.coordinator.async_get_client",
            return_value=client,
        ),
    ):
        yield


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_aioridwell: None
) -> None:
    """Define a fixture to set up ridwell."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
