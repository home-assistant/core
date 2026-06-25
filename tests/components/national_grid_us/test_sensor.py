"""Tests for the National Grid US sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.national_grid_us.const import CONF_ACCOUNT_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    ENTITY_ELECTRIC_COST,
    ENTITY_ELECTRIC_USAGE,
    ENTITY_GAS_COST,
    ENTITY_GAS_USAGE,
    MOCK_ACCOUNT_ID,
    MOCK_ACCOUNT_ID_2,
    MOCK_PASSWORD,
    MOCK_SERVICE_POINT,
    MOCK_USERNAME,
    make_api_mock,
    mock_billing_account,
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


@pytest.mark.usefixtures("mock_national_grid_api")
async def test_meter_devices_linked_to_account_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
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
        identifiers={(DOMAIN, f"{MOCK_ACCOUNT_ID}_{MOCK_SERVICE_POINT}")}
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


async def test_shared_service_point_across_accounts_no_collision(
    hass: HomeAssistant,
) -> None:
    """Test meters sharing a service point across accounts do not collide.

    Two accounts (now two separate config entries) can expose the same
    service point number. Meter devices are keyed by account_id + service
    point so neither overwrites the other and both produce distinct devices
    and sensors.
    """
    entries = []
    for account_id in (MOCK_ACCOUNT_ID, MOCK_ACCOUNT_ID_2):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=account_id,
            data={
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
                CONF_ACCOUNT_ID: account_id,
            },
            unique_id=account_id,
        )
        entry.add_to_hass(hass)
        entries.append(entry)

    def make_account_api() -> AsyncMock:
        api = make_api_mock()
        api.get_billing_account = AsyncMock(side_effect=mock_billing_account)
        return api

    # Setting up one entry sets up the integration, which loads every config
    # entry for the domain, so both accounts are configured in one call.
    with patch(PATCH_CLIENT, side_effect=lambda **kwargs: make_account_api()):
        await hass.config_entries.async_setup(entries[0].entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)

    device_1 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_ACCOUNT_ID}_{MOCK_SERVICE_POINT}")}
    )
    device_2 = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_ACCOUNT_ID_2}_{MOCK_SERVICE_POINT}")}
    )
    assert device_1 is not None
    assert device_2 is not None
    assert device_1.id != device_2.id

    state_1 = hass.states.get(
        f"sensor.electric_meter_{MOCK_ACCOUNT_ID}_sp001_last_billing_usage"
    )
    state_2 = hass.states.get(
        f"sensor.electric_meter_{MOCK_ACCOUNT_ID_2}_sp001_last_billing_usage"
    )
    assert state_1 is not None
    assert state_2 is not None
