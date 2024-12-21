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

    assert response["sensor.rando_brokerage_brokerage_balance"] == (
        '{"CMF":{"quantity":101,"totalValue":202.0,"type":"ETF","percentage":1.3,"name":"iShares S&P CA AMT-Free Municipal Bd",'
        '"sharePrice":2.0,"sharePriceUpdate":"2024-02-16T21:00:04.365428+00:00"},"GOOG":{"quantity":100,"totalValue":10000.0,'
        '"type":"Stock","percentage":65.8,"name":"Google Inc.","sharePrice":100.0,"sharePriceUpdate":"2024-02-16T21:05:46.879464+00:00"},'
        '"CUR:USD":{"quantity":5000,"totalValue":5000.0,"type":"Cash","percentage":32.9,"name":"U S Dollar","sharePrice":1,'
        '"sharePriceUpdate":null}}'
    )
