"""Test services."""

from unittest.mock import AsyncMock

from homeassistant.components.monarch_money.const import (
    DOMAIN,
    GET_HOLDINGS_SERVICE_NAME,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_get_holdings(
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
