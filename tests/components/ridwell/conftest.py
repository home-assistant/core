"""Define test fixtures for Ridwell."""
from datetime import date
from unittest.mock import AsyncMock, Mock, patch

from aioridwell.model import EventState, RidwellPickup, RidwellPickupEvent
import pytest

from homeassistant.components.ridwell.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ACCOUNT_ID = "12345"


@pytest.fixture(name="account")
def account_fixture():
    """Define a Ridwell account."""
    return Mock(
        account_id=ACCOUNT_ID,
        address={
            "street1": "123 Main Street",
            "city": "New York",
            "state": "New York",
            "postal_code": "10001",
        },
        async_get_next_pickup_event=AsyncMock(
            return_value=RidwellPickupEvent(
                None,
                "event_123",
                date(2022, 1, 24),
                [RidwellPickup("Plastic Film", "offer_123", 1, "product_123", 1)],
                EventState.INITIALIZED,
            )
        ),
    )


@pytest.fixture(name="client")
def client_fixture(account):
    """Define an aioridwell client."""
    return Mock(
        async_authenticate=AsyncMock(),
        async_get_accounts=AsyncMock(return_value={ACCOUNT_ID: account}),
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
    }


@pytest.fixture(name="setup_ridwell")
async def setup_ridwell_fixture(hass, client, config):
    """Define a fixture to set up Ridwell."""
    with patch(
        "homeassistant.components.ridwell.config_flow.async_get_client",
        return_value=client,
    ), patch(
        "homeassistant.components.ridwell.async_get_client", return_value=client
    ), patch(
        "homeassistant.components.ridwell.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "user@email.com"
