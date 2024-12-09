"""Tests for switch entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.ohme.switch import (
    OhmeConfigurationSwitch,
    OhmeMaxChargeSwitch,
    OhmePauseChargeSwitch,
    OhmePriceCapSwitch,
    OhmeSolarBoostSwitch,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@pytest.fixture
def mock_hass():
    """Fixture for creating a mock Home Assistant instance."""
    return AsyncMock(spec=HomeAssistant)


@pytest.fixture
def mock_client():
    """Fixture for creating a mock client."""
    client = AsyncMock()
    client.cap_available.return_value = True
    client.solar_capable.return_value = True
    client.is_capable.side_effect = lambda x: x in [
        "buttonsLockable",
        "pluginsRequireApprovalMode",
        "stealth",
    ]
    return client


@pytest.fixture
def mock_coordinator():
    """Fixture for creating a mock coordinator."""
    return AsyncMock(spec=DataUpdateCoordinator)


@pytest.fixture
def mock_config_entry():
    """Fixture for creating a mock config entry."""
    return AsyncMock(data={"email": "test@example.com"})


@pytest.mark.asyncio
async def test_async_setup_entry(mock_hass, mock_config_entry) -> None:
    """Test async_setup_entry."""
    async_add_entities = AsyncMock()
    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)
    assert async_add_entities.call_count == 1
    assert len(async_add_entities.call_args[0][0]) == 7


@pytest.mark.asyncio
async def test_ohme_pause_charge_switch(
    mock_hass, mock_client, mock_coordinator
) -> None:
    """Test OhmePauseChargeSwitch."""
    switch = OhmePauseChargeSwitch(mock_coordinator, mock_hass, mock_client)
    await switch.async_turn_on()
    mock_client.async_pause_charge.assert_called_once()
    await switch.async_turn_off()
    mock_client.async_resume_charge.assert_called_once()


@pytest.mark.asyncio
async def test_ohme_max_charge_switch(mock_hass, mock_client, mock_coordinator) -> None:
    """Test OhmeMaxChargeSwitch."""
    switch = OhmeMaxChargeSwitch(mock_coordinator, mock_hass, mock_client)
    await switch.async_turn_on()
    mock_client.async_max_charge.assert_called_once_with(True)
    mock_client.async_max_charge.reset_mock()
    await switch.async_turn_off()
    mock_client.async_max_charge.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_ohme_configuration_switch(
    mock_hass, mock_client, mock_coordinator
) -> None:
    """Test OhmeConfigurationSwitch."""
    switch = OhmeConfigurationSwitch(
        mock_coordinator,
        mock_hass,
        mock_client,
        "lock_buttons",
        "lock",
        "buttonsLocked",
    )
    await switch.async_turn_on()
    mock_client.async_set_configuration_value.assert_called_once_with(
        {"buttonsLocked": True}
    )
    mock_client.async_set_configuration_value.reset_mock()
    await switch.async_turn_off()
    mock_client.async_set_configuration_value.assert_called_once_with(
        {"buttonsLocked": False}
    )


@pytest.mark.asyncio
async def test_ohme_solar_boost_switch(
    mock_hass, mock_client, mock_coordinator
) -> None:
    """Test OhmeSolarBoostSwitch."""
    switch = OhmeSolarBoostSwitch(mock_coordinator, mock_hass, mock_client)
    await switch.async_turn_on()
    mock_client.async_set_configuration_value.assert_called_once_with(
        {"solarMode": "ZERO_EXPORT"}
    )
    mock_client.async_set_configuration_value.reset_mock()
    await switch.async_turn_off()
    mock_client.async_set_configuration_value.assert_called_once_with(
        {"solarMode": "IGNORE"}
    )


@pytest.mark.asyncio
async def test_ohme_price_cap_switch(mock_hass, mock_client, mock_coordinator) -> None:
    """Test OhmePrice."""
    switch = OhmePriceCapSwitch(mock_coordinator, mock_hass, mock_client)
    await switch.async_turn_on()
    mock_client.async_change_price_cap.assert_called_once_with(enabled=True)
    mock_client.async_change_price_cap.reset_mock()
    await switch.async_turn_off()
    mock_client.async_change_price_cap.assert_called_once_with(enabled=False)
