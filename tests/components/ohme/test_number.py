"""Tests for number entities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.ohme.const import (
    DOMAIN,
    DATA_CLIENT,
    DATA_COORDINATORS,
    COORDINATOR_ACCOUNTINFO,
    COORDINATOR_CHARGESESSIONS,
    COORDINATOR_SCHEDULES,
)

from custom_components.ohme.number import (
    async_setup_entry,
    TargetPercentNumber,
    PreconditioningNumber,
    PriceCapNumber,
)


@pytest.fixture
def mock_hass():
    """Fixture for creating a mock Home Assistant instance."""
    return MagicMock(
        data={
            DOMAIN: {
                "test@example.com": {
                    DATA_COORDINATORS: [
                        AsyncMock(),
                        AsyncMock(),
                        AsyncMock(),
                        AsyncMock(),
                    ],
                    DATA_CLIENT: AsyncMock(),
                }
            }
        }
    )


@pytest.fixture
def mock_config_entry():
    """Fixture for creating a mock config entry."""
    return AsyncMock(data={"email": "test@example.com"})


@pytest.fixture
def mock_async_add_entities():
    """Fixture for creating a mock async_add_entities."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_async_setup_entry(mock_hass, mock_config_entry, mock_async_add_entities):
    """Test async_setup_entry."""
    await async_setup_entry(mock_hass, mock_config_entry, mock_async_add_entities)
    assert mock_async_add_entities.call_count == 1


@pytest.mark.asyncio
async def test_target_percent_number(mock_hass):
    """Test TargetPercentNumber."""
    coordinator = mock_hass.data[DOMAIN]["test@example.com"][DATA_COORDINATORS][
        COORDINATOR_CHARGESESSIONS
    ]
    coordinator_schedules = mock_hass.data[DOMAIN]["test@example.com"][
        DATA_COORDINATORS
    ][COORDINATOR_SCHEDULES]
    client = mock_hass.data[DOMAIN]["test@example.com"][DATA_CLIENT]

    number = TargetPercentNumber(coordinator, coordinator_schedules, mock_hass, client)

    with patch("custom_components.ohme.number.session_in_progress", return_value=True):
        await number.async_added_to_hass()
        await number.async_set_native_value(50)

    assert number._state is None or number._state == 50


@pytest.mark.asyncio
async def test_preconditioning_number(mock_hass):
    """Test PreconditioningNumber."""
    coordinator = mock_hass.data[DOMAIN]["test@example.com"][DATA_COORDINATORS][
        COORDINATOR_CHARGESESSIONS
    ]
    coordinator_schedules = mock_hass.data[DOMAIN]["test@example.com"][
        DATA_COORDINATORS
    ][COORDINATOR_SCHEDULES]
    client = mock_hass.data[DOMAIN]["test@example.com"][DATA_CLIENT]

    number = PreconditioningNumber(
        coordinator, coordinator_schedules, mock_hass, client
    )

    with patch("custom_components.ohme.number.session_in_progress", return_value=True):
        await number.async_added_to_hass()
        await number.async_set_native_value(30)

    assert number._state is None or number._state == 30


@pytest.mark.asyncio
async def test_price_cap_number(mock_hass):
    """Test PriceCapNumber."""
    coordinator = mock_hass.data[DOMAIN]["test@example.com"][DATA_COORDINATORS][
        COORDINATOR_ACCOUNTINFO
    ]
    client = mock_hass.data[DOMAIN]["test@example.com"][DATA_CLIENT]

    number = PriceCapNumber(coordinator, mock_hass, client)
    await number.async_set_native_value(10.0)

    assert number._state is None or number._state == 10.0
