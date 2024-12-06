import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from custom_components.ohme.button import async_setup_entry, OhmeApproveChargeButton
from custom_components.ohme.const import (
    DOMAIN,
    DATA_CLIENT,
    DATA_COORDINATORS,
    COORDINATOR_CHARGESESSIONS,
)


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_account": {}}}
    return hass


@pytest.fixture
def mock_config_entry():
    return AsyncMock(data={"email": "test@example.com"})


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.is_capable.return_value = True
    client.async_approve_charge = AsyncMock()
    return client


@pytest.fixture
def mock_coordinator():
    coordinator = AsyncMock()
    coordinator.async_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def setup_hass(mock_hass, mock_config_entry, mock_client, mock_coordinator):
    mock_hass.data = {
        DOMAIN: {
            "test@example.com": {
                DATA_CLIENT: mock_client,
                DATA_COORDINATORS: {COORDINATOR_CHARGESESSIONS: mock_coordinator},
            }
        }
    }
    return mock_hass


@pytest.mark.asyncio
async def test_async_setup_entry(setup_hass, mock_config_entry):
    async_add_entities = AsyncMock()
    await async_setup_entry(setup_hass, mock_config_entry, async_add_entities)
    assert async_add_entities.call_count == 1


@pytest.mark.asyncio
async def test_ohme_approve_charge_button(setup_hass, mock_client, mock_coordinator):
    button = OhmeApproveChargeButton(mock_coordinator, setup_hass, mock_client)
    await button.async_press()
    mock_client.async_approve_charge.assert_called_once()
    mock_coordinator.async_refresh.assert_called_once()
