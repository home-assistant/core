"""Test V2C actions."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from pytrydan.exceptions import TrydanError

from homeassistant.components.v2c.const import DOMAIN
from homeassistant.components.v2c.services import V2CService, V2CServiceArgument
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr

from . import init_integration


@pytest.fixture
async def device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_v2c_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> dr.DeviceEntry:
    """Set up the charger and return its device."""
    await init_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    return device


@pytest.mark.parametrize("power", [4600, 0, -500])
async def test_set_contracted_power(
    hass: HomeAssistant, mock_v2c_client: AsyncMock, device: dr.DeviceEntry, power: int
) -> None:
    """Test the device's signed power value is passed to the library."""
    await hass.services.async_call(
        DOMAIN,
        V2CService.SET_CONTRACTED_POWER,
        {ATTR_DEVICE_ID: device.id, V2CServiceArgument.POWER: power},
        blocking=True,
    )
    mock_v2c_client.contracted_power.assert_awaited_once_with(power)


async def test_set_contracted_power_failure(
    hass: HomeAssistant, mock_v2c_client: AsyncMock, device: dr.DeviceEntry
) -> None:
    """Test library failures are reported."""
    mock_v2c_client.contracted_power.side_effect = TrydanError
    with pytest.raises(HomeAssistantError, match="Failed to set"):
        await hass.services.async_call(
            DOMAIN,
            V2CService.SET_CONTRACTED_POWER,
            {ATTR_DEVICE_ID: device.id, V2CServiceArgument.POWER: -500},
            blocking=True,
        )


@pytest.mark.usefixtures("device")
async def test_set_contracted_power_unknown_device(hass: HomeAssistant) -> None:
    """Test an unknown charger is rejected."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            V2CService.SET_CONTRACTED_POWER,
            {ATTR_DEVICE_ID: "unknown", V2CServiceArgument.POWER: 4600},
            blocking=True,
        )


async def test_set_contracted_power_requires_admin(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    mock_v2c_client: AsyncMock,
    device: dr.DeviceEntry,
) -> None:
    """Test only administrators can change the setting."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            V2CService.SET_CONTRACTED_POWER,
            {ATTR_DEVICE_ID: device.id, V2CServiceArgument.POWER: 4600},
            context=Context(user_id=hass_read_only_user.id),
            blocking=True,
        )
    mock_v2c_client.contracted_power.assert_not_called()
