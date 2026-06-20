"""Tests for the National Grid US sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.national_grid_us.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    ENTITY_ELECTRIC_COST,
    ENTITY_ELECTRIC_USAGE,
    ENTITY_GAS_COST,
    ENTITY_GAS_USAGE,
    MOCK_ACCOUNT_ID,
    MOCK_SERVICE_POINT,
    make_api_mock,
)

from tests.common import MockConfigEntry

PATCH_CLIENT = (
    "homeassistant.components.national_grid_us.coordinator.NationalGridClient"
)


@pytest.mark.usefixtures("mock_national_grid_api")
async def test_sensor_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensor entities are created for each meter."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Electric meter - usage (kWh, no conversion)
    state = hass.states.get(ENTITY_ELECTRIC_USAGE)
    assert state is not None
    assert float(state.state) == 500.0

    # Electric meter - cost
    state = hass.states.get(ENTITY_ELECTRIC_COST)
    assert state is not None
    assert float(state.state) == 120.5

    # Gas meter - usage (CCF converted to m³ by HA)
    state = hass.states.get(ENTITY_GAS_USAGE)
    assert state is not None
    assert float(state.state) > 0

    # Gas meter - cost
    state = hass.states.get(ENTITY_GAS_COST)
    assert state is not None
    assert float(state.state) == 45.0


async def test_meter_devices_linked_to_account_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test meter devices are linked to a pre-registered account device."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)

    account_device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_ACCOUNT_ID)}
    )
    assert account_device is not None
    assert account_device.entry_type is dr.DeviceEntryType.SERVICE

    meter_device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERVICE_POINT)}
    )
    assert meter_device is not None
    assert meter_device.via_device_id == account_device.id


async def test_cost_sensor_uses_date_not_month_across_year_boundary(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the cost sensor picks the most recent cost by date, not month number.

    Regression: "month" is 1-12 only (not year-aware). The previous year's
    December (month=12) must not be returned over a more recent January
    (month=1) of the following year.
    """
    api = make_api_mock()
    api.get_energy_usage_costs = AsyncMock(
        return_value=[
            {
                "fuelType": "ELECTRIC",
                "month": 12,
                "date": "2024-12-01",
                "amount": 140.00,
            },
            {
                "fuelType": "ELECTRIC",
                "month": 1,
                "date": "2025-01-01",
                "amount": 120.50,
            },
        ]
    )

    with patch(PATCH_CLIENT, return_value=api):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ELECTRIC_COST)
    assert state is not None
    assert float(state.state) == 120.5
