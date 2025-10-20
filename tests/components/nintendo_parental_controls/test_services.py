"""Test Nintendo Parental Controls service calls."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.nintendo_parental_controls.const import (
    ATTR_BONUS_TIME,
    DOMAIN,
)
from homeassistant.components.nintendo_parental_controls.services import (
    NintendoParentalServices,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_add_bonus_time(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test add bonus time service."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "testdevid")})
    assert device_entry
    await hass.services.async_call(
        DOMAIN,
        NintendoParentalServices.ADD_BONUS_TIME,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_DEVICE_ID: device_entry.id,
            ATTR_BONUS_TIME: 15,
        },
        blocking=True,
    )
    assert len(mock_nintendo_device.add_extra_time.mock_calls) == 1


async def test_add_bonus_time_invalid_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
) -> None:
    """Test add bonus time service."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "testdevid")})
    assert device_entry
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            NintendoParentalServices.ADD_BONUS_TIME,
            {
                ATTR_CONFIG_ENTRY_ID: "ABC123",
                ATTR_DEVICE_ID: device_entry.id,
                ATTR_BONUS_TIME: 15,
            },
            blocking=True,
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "config_entry_not_found"


async def test_add_bonus_time_invalid_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
) -> None:
    """Test add bonus time service."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            NintendoParentalServices.ADD_BONUS_TIME,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_DEVICE_ID: "invalid_device_id",
                ATTR_BONUS_TIME: 15,
            },
            blocking=True,
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "device_not_found"
