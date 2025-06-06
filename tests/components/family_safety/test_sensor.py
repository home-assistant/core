"""Test sensor platform for family safety."""

from unittest.mock import AsyncMock

from homeassistant.components.family_safety.coordinator import FamilySafetyConfigEntry
from homeassistant.components.family_safety.sensor import (
    SENSOR_DESCRIPTIONS,
    FamilySafetySensor,
    FamilySafetySensorEntity,
    FamilySafetySensorEntityDescription,
    async_setup_entry,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .conftest import MockAccount


async def test_family_safety_sensor_entity_init(
    mock_coordinator_with_api: AsyncMock,
    mock_account_data: MockAccount,
) -> None:
    """Test the initialization of a FamilySafetySensorEntity."""
    description = FamilySafetySensorEntityDescription(
        key=FamilySafetySensor.PLAYING_TIME,
        translation_key=FamilySafetySensor.PLAYING_TIME,
        value_fn=lambda device: 0,  # Dummy function for init test
    )
    entity = FamilySafetySensorEntity(
        coordinator=mock_coordinator_with_api,
        account=mock_account_data,
        description=description,
    )

    # Verify base FamilySafetyDevice init is called correctly
    assert entity.coordinator == mock_coordinator_with_api
    assert entity.account == mock_account_data
    assert entity._attr_unique_id == f"{mock_account_data.user_id}_{description.key}"
    assert entity.entity_description == description
    assert entity._attr_has_entity_name is True  # Inherited from FamilySafetyDevice


async def test_family_safety_sensor_playing_time_native_value(
    mock_coordinator_with_api: AsyncMock,
    mock_account_data: MockAccount,
) -> None:
    """Test native_value for PLAYING_TIME sensor."""
    description = next(
        d for d in SENSOR_DESCRIPTIONS if d.key == FamilySafetySensor.PLAYING_TIME
    )
    entity = FamilySafetySensorEntity(
        coordinator=mock_coordinator_with_api,
        account=mock_account_data,
        description=description,
    )

    # The mock_account_data has today_screentime_usage = 120 minutes (in ms)
    # value_fn is device.account.today_screentime_usage / 1000 / 60
    expected_value = 120  # minutes
    assert entity.native_value == expected_value
    assert entity.native_unit_of_measurement == UnitOfTime.MINUTES


async def test_family_safety_sensor_account_balance_native_value(
    mock_coordinator_with_api: AsyncMock,
    mock_account_data: MockAccount,
) -> None:
    """Test native_value and native_unit_of_measurement for ACCOUNT_BALANCE sensor."""
    description = next(
        d for d in SENSOR_DESCRIPTIONS if d.key == FamilySafetySensor.ACCOUNT_BALANCE
    )
    entity = FamilySafetySensorEntity(
        coordinator=mock_coordinator_with_api,
        account=mock_account_data,
        description=description,
    )

    # The mock_account_data has account_balance = 25.50
    # value_fn is device.account.account_balance
    expected_value = 25.50
    assert entity.native_value == expected_value
    assert (
        entity.native_unit_of_measurement == mock_account_data.account_currency
    )  # "USD"


async def test_family_safety_sensor_pending_requests_native_value(
    mock_coordinator_with_api: AsyncMock,
    mock_account_data: MockAccount,
) -> None:
    """Test native_value for PENDING_REQUESTS sensor."""
    description = next(
        d for d in SENSOR_DESCRIPTIONS if d.key == FamilySafetySensor.PENDING_REQUESTS
    )
    entity = FamilySafetySensorEntity(
        coordinator=mock_coordinator_with_api,
        account=mock_account_data,
        description=description,
    )

    # Simulate 3 pending requests
    mock_coordinator_with_api.api.get_account_requests.return_value = [
        "req1",
        "req2",
        "req3",
    ]
    # value_fn is len(device.coordinator.api.get_account_requests(device.account.user_id))
    expected_value = 3
    assert entity.native_value == expected_value
    mock_coordinator_with_api.api.get_account_requests.assert_called_once_with(
        mock_account_data.user_id
    )
    assert entity.native_unit_of_measurement is None  # No unit of measurement for count


async def test_async_setup_entry_single_account(
    hass: HomeAssistant,
    mock_coordinator_with_api: AsyncMock,
    mock_add_entities: AddConfigEntryEntitiesCallback,
    mock_account_data: MockAccount,
) -> None:
    """Test async_setup_entry with a single account."""
    # Configure the mock coordinator to have one account
    mock_coordinator_with_api.api.accounts = [mock_account_data]

    # Create a mock config entry
    mock_entry = AsyncMock(spec=FamilySafetyConfigEntry)
    mock_entry.runtime_data = mock_coordinator_with_api

    await async_setup_entry(hass, mock_entry, mock_add_entities)

    # Expect one entity to be added for each SENSOR_DESCRIPTION for the single account
    expected_calls = len(SENSOR_DESCRIPTIONS)

    # Assert that async_add_entities was called once
    mock_add_entities.assert_called_once()

    # Get the list of entities that would be added
    entities_added = list(mock_add_entities.call_args[0][0])
    assert len(entities_added) == expected_calls

    # Verify types and basic attributes of created entities
    for entity in entities_added:
        assert isinstance(entity, FamilySafetySensorEntity)
        assert entity.coordinator == mock_coordinator_with_api
        assert entity.account == mock_account_data
        assert any(
            entity.entity_description.key == desc.key for desc in SENSOR_DESCRIPTIONS
        )


async def test_async_setup_entry_multiple_accounts(
    hass: HomeAssistant,
    mock_coordinator_with_api: AsyncMock,
    mock_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Test async_setup_entry with multiple accounts."""
    account1 = MockAccount("user_a", "Alice", "A")
    account2 = MockAccount("user_b", "Bob", "B")
    mock_coordinator_with_api.api.accounts = [account1, account2]

    mock_entry = AsyncMock(spec=FamilySafetyConfigEntry)
    mock_entry.runtime_data = mock_coordinator_with_api

    await async_setup_entry(hass, mock_entry, mock_add_entities)

    expected_total_entities = len(mock_coordinator_with_api.api.accounts) * len(
        SENSOR_DESCRIPTIONS
    )

    mock_add_entities.assert_called_once()
    entities_added = list(mock_add_entities.call_args[0][0])
    assert len(entities_added) == expected_total_entities

    # Optional: More granular checks to ensure correct entities are created per account
    user_ids_in_entities = {entity.account.user_id for entity in entities_added}
    assert user_ids_in_entities == {"user_a", "user_b"}

    keys_per_user = {
        user_id: {
            entity.entity_description.key
            for entity in entities_added
            if entity.account.user_id == user_id
        }
        for user_id in user_ids_in_entities
    }
    assert keys_per_user["user_a"] == {desc.key for desc in SENSOR_DESCRIPTIONS}
    assert keys_per_user["user_b"] == {desc.key for desc in SENSOR_DESCRIPTIONS}
