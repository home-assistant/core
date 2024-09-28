"""Test SimpleFin Sensor with Snapshot data."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from simplefin4py.exceptions import SimpleFinAuthError, SimpleFinPaymentRequiredError
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_simplefin_client: AsyncMock,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.simplefin.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("side_effect"),
    [
        (SimpleFinAuthError),
        (SimpleFinPaymentRequiredError),
    ],
)
async def test_update_errors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_simplefin_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """Test connection error."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.the_bank_of_go_the_bank_balance").state == "7777.77"
    assert hass.states.get("sensor.investments_my_checking_balance").state == "12345.67"
    assert (
        hass.states.get("sensor.the_bank_of_go_prime_savings_balance").state
        == "9876.54"
    )
    assert (
        hass.states.get("sensor.random_bank_costco_anywhere_visa_r_card_balance").state
        == "-532.69"
    )
    assert hass.states.get("sensor.investments_dr_evil_balance").state == "1000000.00"
    assert (
        hass.states.get("sensor.investments_nerdcorp_series_b_balance").state
        == "13579.24"
    )
    assert (
        hass.states.get("sensor.mythical_randomsavings_unicorn_pot_balance").state
        == "10000.00"
    )
    assert (
        hass.states.get("sensor.mythical_randomsavings_castle_mortgage_balance").state
        == "7500.00"
    )

    mock_simplefin_client.return_value.fetch_data.side_effect = side_effect
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    sensors = [
        "sensor.the_bank_of_go_the_bank_balance",
        "sensor.investments_my_checking_balance",
        "sensor.the_bank_of_go_prime_savings_balance",
        "sensor.random_bank_costco_anywhere_visa_r_card_balance",
        "sensor.investments_dr_evil_balance",
        "sensor.investments_nerdcorp_series_b_balance",
        "sensor.mythical_randomsavings_unicorn_pot_balance",
        "sensor.mythical_randomsavings_castle_mortgage_balance",
    ]

    for sensor in sensors:
        assert hass.states.get(sensor).state == STATE_UNAVAILABLE
