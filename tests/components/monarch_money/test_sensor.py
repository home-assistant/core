"""Test sensors."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from typedmonarchmoney.models import MonarchBudget

from homeassistant.components.monarch_money.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


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

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    vacation_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, vacation_unique_id
    )
    assert vacation_entity_id is not None

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    vacation_state = hass.states.get(vacation_entity_id)
    assert vacation_state is not None
    assert vacation_state.state == "unavailable"

    await coordinator.async_refresh()
    await hass.async_block_till_done()
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

    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

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
