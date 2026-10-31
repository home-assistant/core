"""Test sensors."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from typedmonarchmoney.models import MonarchBudget

from homeassistant.components.monarch_money.config_flow import MonarchMoneyConfigFlow
from homeassistant.components.monarch_money.const import DEFAULT_CURRENCY, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import PERCENTAGE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all entities."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-09-20T12:00:00+00:00")
    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_budget_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test budget sensors preserve rollovers and missing amounts."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-09-20T12:00:00+00:00")
    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    subscription_id = (
        mock_config_api.return_value.get_subscription_details.return_value.id
    )
    actual_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{subscription_id}_budget_category-food_actual"
    )
    planned_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{subscription_id}_budget_category-food_planned"
    )
    remaining_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{subscription_id}_budget_category-food_remaining"
    )
    missing_value_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{subscription_id}_budget_category-vacation_actual"
    )

    assert actual_entity_id is not None
    assert planned_entity_id is not None
    assert remaining_entity_id is not None
    assert missing_value_entity_id is not None
    actual_entry = entity_registry.async_get(actual_entity_id)
    planned_entry = entity_registry.async_get(planned_entity_id)
    remaining_entry = entity_registry.async_get(remaining_entity_id)
    assert actual_entry is not None
    assert planned_entry is not None
    assert remaining_entry is not None
    assert actual_entry.device_id is not None
    assert (
        actual_entry.device_id == planned_entry.device_id == remaining_entry.device_id
    )

    device = device_registry.async_get(actual_entry.device_id)
    assert device is not None
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert (DOMAIN, f"{subscription_id}_budget_category-food") in device.identifiers

    actual_state = hass.states.get(actual_entity_id)
    assert actual_state is not None
    remaining_state = hass.states.get(remaining_entity_id)
    missing_value_state = hass.states.get(missing_value_entity_id)
    assert remaining_state is not None
    assert missing_value_state is not None
    assert remaining_state.state == "625.0"
    assert missing_value_state.state == "unknown"
    assert (
        actual_state.attributes["last_reset"]
        == dt_util.start_of_local_day(dt_util.now().replace(day=1)).isoformat()
    )


async def test_budget_sensors_discover_and_recover_categories(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test budget categories are added later and recover after missing data."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-09-20T12:00:00+00:00")
    budget_data = (
        mock_config_api.return_value.get_budgets_as_dict_with_id_key.return_value
    )
    budget_data_without_vacation = {"category-food": budget_data["category-food"]}
    mock_config_api.return_value.get_budgets_as_dict_with_id_key.side_effect = [
        budget_data_without_vacation,
        budget_data,
        budget_data_without_vacation,
        budget_data,
    ]

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    subscription_id = (
        mock_config_api.return_value.get_subscription_details.return_value.id
    )
    vacation_unique_id = f"{subscription_id}_budget_category-vacation_actual"
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, vacation_unique_id)
        is None
    )

    freezer.tick(timedelta(hours=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    vacation_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, vacation_unique_id
    )
    assert vacation_entity_id is not None

    freezer.tick(timedelta(hours=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    vacation_state = hass.states.get(vacation_entity_id)
    assert vacation_state is not None
    assert vacation_state.state == "unavailable"

    freezer.tick(timedelta(hours=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    vacation_state = hass.states.get(vacation_entity_id)
    assert vacation_state is not None
    assert vacation_state.state == "unknown"


@pytest.mark.parametrize(
    ("category_id", "monthly_amounts"),
    [
        pytest.param(
            "category-stale",
            [
                {
                    "month": "2026-08-01",
                    "plannedCashFlowAmount": -1200.0,
                    "actualAmount": -1200.0,
                    "remainingAmount": 0.0,
                }
            ],
            id="stale_month_only",
        ),
        pytest.param(
            "category-without-amounts",
            [],
            id="no_monthly_record",
        ),
    ],
)
async def test_budget_sensors_recover_when_current_month_appears(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
    category_id: str,
    monthly_amounts: list[dict[str, str | float]],
) -> None:
    """Test a known budget starts unavailable until its current month appears."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-09-20T12:00:00+00:00")
    budget_data = deepcopy(
        mock_config_api.return_value.get_budgets_as_dict_with_id_key.return_value
    )
    budget_data[category_id] = MonarchBudget(
        {"id": category_id, "name": "Test budget"},
        group_name="Test budgets",
        monthly_amounts=monthly_amounts,
    )
    budget_data_with_current_month = deepcopy(budget_data)
    budget_data_with_current_month[category_id] = MonarchBudget(
        {"id": category_id, "name": "Test budget"},
        group_name="Test budgets",
        monthly_amounts=[
            {
                "month": "2026-09-01",
                "plannedCashFlowAmount": -1200.0,
                "actualAmount": -400.0,
                "remainingAmount": 800.0,
            }
        ],
    )
    mock_config_api.return_value.get_budgets_as_dict_with_id_key.side_effect = [
        budget_data,
        budget_data_with_current_month,
    ]

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    subscription_id = (
        mock_config_api.return_value.get_subscription_details.return_value.id
    )
    budget_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{subscription_id}_budget_{category_id}_actual"
    )
    assert budget_entity_id is not None
    budget_state = hass.states.get(budget_entity_id)
    assert budget_state is not None
    assert budget_state.state == "unavailable"

    freezer.tick(timedelta(hours=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    budget_state = hass.states.get(budget_entity_id)
    assert budget_state is not None
    assert budget_state.state == "-400.0"


@pytest.mark.parametrize(
    ("account_owner", "expected_state"),
    [
        pytest.param(
            {"id": "900000010", "displayName": "Alex"},
            "Alex",
            id="display_name",
        ),
        pytest.param(
            {"id": "900000010", "displayName": "", "name": "Alex"},
            "Alex",
            id="name_fallback",
        ),
        pytest.param(
            {"id": "900000010", "displayName": "  ", "name": "  "},
            "unknown",
            id="empty_names",
        ),
        pytest.param(None, "unknown", id="no_owner"),
    ],
)
async def test_account_owner_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    entity_registry: er.EntityRegistry,
    account_owner: dict[str, str] | None,
    expected_state: str,
) -> None:
    """Test the account owner is exposed as a sensor on the account device."""
    account = mock_config_api.return_value.get_accounts.return_value[0]
    account.account_owner = account_owner
    mock_config_api.return_value.get_accounts_as_dict_with_id_key.return_value[
        account.id
    ].account_owner = account_owner

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    subscription_id = (
        mock_config_api.return_value.get_subscription_details.return_value.id
    )
    owner_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{subscription_id}_{account.id}_owner"
    )
    age_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{subscription_id}_{account.id}_age"
    )

    assert owner_entity_id is not None
    assert age_entity_id is not None
    owner_state = hass.states.get(owner_entity_id)
    age_state = hass.states.get(age_entity_id)
    assert owner_state is not None
    assert age_state is not None
    assert owner_state.state == expected_state
    assert "account_owner" not in age_state.attributes
    owner_entry = entity_registry.async_get(owner_entity_id)
    age_entry = entity_registry.async_get(age_entity_id)
    assert owner_entry is not None
    assert age_entry is not None
    assert owner_entry.device_id == age_entry.device_id


@pytest.mark.parametrize(
    "currency",
    [
        "USD",
        "CAD",
        "EUR",
        "GBP",
    ],
)
async def test_monetary_sensors_ignore_hass_currency(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
    currency: str,
) -> None:
    """Test that monetary sensors ignore the configured HA currency."""
    await hass.config.async_update(country="US", currency=currency)

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    for unique_id in (
        "222260252323873333_900000002_balance",
        "222260252323873333_cashflow_sum_income",
        "222260252323873333_121212192626186051_value",
        "222260252323873333_budget_category-food_actual",
    ):
        entity_id = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, unique_id
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["unit_of_measurement"] == DEFAULT_CURRENCY
        assert state.attributes["device_class"] == "monetary"


async def test_non_monetary_sensors_not_affected_by_currency(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test that non-monetary sensors are not affected by currency setting."""
    await hass.config.async_update(country="US", currency="CAD")

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    age_entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, "222260252323873333_900000002_age"
    )
    assert age_entity_id is not None
    state = hass.states.get(age_entity_id)
    assert state is not None
    assert state.attributes["device_class"] == "timestamp"
    assert "unit_of_measurement" not in state.attributes

    savings_rate_entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, "222260252323873333_cashflow_savings_rate"
    )
    assert savings_rate_entity_id is not None
    state = hass.states.get(savings_rate_entity_id)
    assert state is not None
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    assert "device_class" not in state.attributes


@pytest.mark.usefixtures("mock_setup_entry", "recorder_mock")
async def test_statistics_migration_called_for_monetary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test statistics migration updates existing monetary sensors."""
    await hass.config.async_update(country="US", currency="USD")

    mock_config_entry.add_to_hass(hass)
    _add_migration_entity_registry_entries(entity_registry, mock_config_entry)

    with patch(
        "homeassistant.components.monarch_money.async_update_statistics_metadata"
    ) as mock_update_stats:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    called_entity_ids = {call.args[1] for call in mock_update_stats.call_args_list}
    assert called_entity_ids == {
        "sensor.cashflow_income_year_to_date",
        "sensor.rando_bank_checking_balance",
    }
    for call in mock_update_stats.call_args_list:
        assert call.kwargs["new_unit_of_measurement"] == DEFAULT_CURRENCY

    assert mock_config_entry.minor_version == MonarchMoneyConfigFlow.MINOR_VERSION


@pytest.mark.usefixtures("mock_setup_entry")
async def test_statistics_migration_skips_metadata_without_recorder(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test statistics migration skips metadata updates without recorder."""
    mock_config_entry.add_to_hass(hass)
    _add_migration_entity_registry_entries(entity_registry, mock_config_entry)

    with patch(
        "homeassistant.components.monarch_money.async_update_statistics_metadata",
        side_effect=AssertionError("Statistics metadata should not be updated"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.minor_version == MonarchMoneyConfigFlow.MINOR_VERSION


def _add_migration_entity_registry_entries(
    entity_registry: er.EntityRegistry, mock_config_entry: MockConfigEntry
) -> None:
    """Add entity registry entries for statistics migration tests."""
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "222260252323873333_checking_currentBalance",
        config_entry=mock_config_entry,
        original_device_class=SensorDeviceClass.MONETARY,
        suggested_object_id="rando_bank_checking_balance",
    )
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "222260252323873333_sum_income",
        config_entry=mock_config_entry,
        original_device_class=SensorDeviceClass.MONETARY,
        suggested_object_id="cashflow_income_year_to_date",
    )
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "222260252323873333_checking_age",
        config_entry=mock_config_entry,
        original_device_class=SensorDeviceClass.TIMESTAMP,
        suggested_object_id="rando_bank_checking_data_age",
    )
