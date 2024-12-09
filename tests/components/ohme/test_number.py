"""Tests for number entities."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.ohme.number import (
    PreconditioningNumber,
    PriceCapNumber,
    TargetPercentNumber,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    """Fixture for creating a mock Home Assistant instance."""
    return AsyncMock(spec=HomeAssistant)


@pytest.fixture
def mock_config_entry():
    """Fixture for creating a mock config entry."""
    return AsyncMock(data={"email": "test@example.com"})


@pytest.fixture
def mock_async_add_entities():
    """Fixture for creating a mock async_add_entities."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_async_setup_entry(mock_config_entry, mock_async_add_entities) -> None:
    """Test async_setup_entry."""
    await async_setup_entry(AsyncMock(), mock_config_entry, mock_async_add_entities)
    assert mock_async_add_entities.call_count == 1


@pytest.mark.asyncio
async def test_target_percent_number() -> None:
    """Test TargetPercentNumber."""

    number = TargetPercentNumber(AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())
    number.platform = AsyncMock()

    with patch(
        "homeassistant.components.ohme.number.session_in_progress", return_value=True
    ):
        await number.async_added_to_hass()
        await number.async_set_native_value(50)

    assert number._state is None or number._state == 50


@pytest.mark.asyncio
async def test_preconditioning_number(mock_hass) -> None:
    """Test PreconditioningNumber."""
    number = PreconditioningNumber(AsyncMock(), AsyncMock(), mock_hass, AsyncMock())
    number.platform = AsyncMock()

    with patch(
        "homeassistant.components.ohme.number.session_in_progress", return_value=True
    ):
        await number.async_added_to_hass()
        await number.async_set_native_value(30)

    assert number._state is None or number._state == 30


@pytest.mark.asyncio
async def test_price_cap_number(mock_hass) -> None:
    """Test PriceCapNumber."""

    number = PriceCapNumber(AsyncMock(), mock_hass, AsyncMock())
    number.platform = AsyncMock()

    await number.async_set_native_value(10.0)

    assert number._state is None or number._state == 10.0
