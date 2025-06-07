"""Test base entity definition of Family Safety."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.family_safety.const import DOMAIN
from homeassistant.components.family_safety.entity import FamilySafetyDevice
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .conftest import TEST_ACCOUNT_NAME, TEST_KEY, TEST_USER_ID, MockAccount


async def test_family_safety_device_init(
    mock_coordinator: AsyncMock, mock_account: MockAccount
) -> None:
    """Test the initialization of FamilySafetyDevice."""
    entity = FamilySafetyDevice(mock_coordinator, mock_account, TEST_KEY)
    assert entity._attr_has_entity_name is True
    expected_unique_id = f"{TEST_USER_ID}_{TEST_KEY}"
    assert entity._attr_unique_id == expected_unique_id
    expected_device_info = DeviceInfo(
        identifiers={(DOMAIN, TEST_USER_ID)},
        manufacturer="Microsoft",
        name=TEST_ACCOUNT_NAME,
    )
    assert entity._attr_device_info == expected_device_info
    assert entity.account == mock_account
    assert entity.coordinator == mock_coordinator


async def test_family_safety_device_async_added_to_hass(
    mock_coordinator: AsyncMock, mock_account: MockAccount
) -> None:
    """Test async_added_to_hass lifecycle method."""
    entity = FamilySafetyDevice(mock_coordinator, mock_account, TEST_KEY)
    with patch.object(
        CoordinatorEntity, "async_added_to_hass", new=AsyncMock()
    ) as mock_super_added:
        await entity.async_added_to_hass()
        mock_super_added.assert_awaited_once()
        mock_account.add_account_callback.assert_called_once_with(
            entity.async_write_ha_state
        )


async def test_family_safety_device_async_removed_from_registry(
    mock_coordinator: AsyncMock, mock_account: MockAccount
) -> None:
    """Test async_removed_from_registry lifecycle method."""
    entity = FamilySafetyDevice(mock_coordinator, mock_account, TEST_KEY)
    with patch.object(
        CoordinatorEntity, "async_removed_from_registry", new=AsyncMock()
    ) as mock_super_removed:
        await entity.async_removed_from_registry()
        mock_super_removed.assert_awaited_once()
        mock_account.remove_account_callback.assert_called_once_with(
            entity.async_write_ha_state
        )
