"""Test services."""

import json
from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.monarch_money.const import (
    DOMAIN,
    GET_HOLDINGS_SERVICE_NAME,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_get_no_holdings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test holding services."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        GET_HOLDINGS_SERVICE_NAME,
        {ATTR_ENTITY_ID: "sensor.rando_employer_investments_401_k_data_age"},
        blocking=True,
        return_response=True,
    )

    assert response == {"sensor.rando_employer_investments_401_k_data_age": "{}"}


async def test_get_holdings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test holding services."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        GET_HOLDINGS_SERVICE_NAME,
        {ATTR_ENTITY_ID: "sensor.rando_brokerage_brokerage_balance"},
        blocking=True,
        return_response=True,
    )

    assert response == snapshot

    # Test the structure contains expected keys for one holding as a sanity check
    holdings_data = json.loads(response["sensor.rando_brokerage_brokerage_balance"])
    assert "CMF" in holdings_data
    assert "quantity" in holdings_data["CMF"]
