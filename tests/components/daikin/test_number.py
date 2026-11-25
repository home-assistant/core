"""Tests for Daikin number entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.daikin.const import DOMAIN
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberService,
    NumberServiceArgument,
)
from homeassistant.const import CommonServiceArgument, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import ZoneDevice, async_setup_daikin


def _demand_control_number_entity_id(
    entity_registry: er.EntityRegistry, mac: str
) -> str | None:
    """Return the demand control number entity ID."""
    return entity_registry.async_get_entity_id(
        NUMBER_DOMAIN, DOMAIN, f"{mac}-demand_control_max_power"
    )


@pytest.mark.parametrize(
    ("demand_control", "expected_power"),
    [
        pytest.param({"en_demand": "1", "mode": "0", "max_pow": "50"}, "50"),
        pytest.param({"en_demand": "1", "mode": "2", "max_pow": "60"}, "60"),
        pytest.param({"en_demand": "0", "mode": "0", "max_pow": "70"}, "70"),
        pytest.param({"en_demand": "0", "mode": "2", "max_pow": "80"}, "80"),
    ],
)
async def test_number_demand_control_max_power_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    demand_control: dict[str, str],
    expected_power: str,
) -> None:
    """Test demand control number state and category."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control.return_value = demand_control

    await async_setup_daikin(hass, zone_device)

    entity_id = _demand_control_number_entity_id(entity_registry, zone_device.mac)
    assert entity_id is not None
    assert (state := hass.states.get(entity_id))
    assert state.state == expected_power
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.entity_category is EntityCategory.CONFIG


async def test_number_demand_control_max_power_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Do not create a demand control number when unsupported."""
    await async_setup_daikin(hass, zone_device)

    assert _demand_control_number_entity_id(entity_registry, zone_device.mac) is None


@pytest.mark.parametrize(
    ("demand_control", "expected_enabled", "expected_mode"),
    [
        pytest.param(
            {"en_demand": "1", "mode": "0", "max_pow": "50"},
            "on",
            0,
            id="enabled-manual",
        ),
        pytest.param(
            {"en_demand": "1", "mode": "2", "max_pow": "50"},
            "on",
            2,
            id="enabled-auto",
        ),
        pytest.param(
            {"en_demand": "0", "mode": "0", "max_pow": "50"},
            "off",
            0,
            id="disabled-manual",
        ),
        pytest.param(
            {"en_demand": "0", "mode": "2", "max_pow": "50"},
            "off",
            2,
            id="disabled-auto",
        ),
    ],
)
async def test_set_demand_control_max_power(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    demand_control: dict[str, str],
    expected_enabled: str,
    expected_mode: int,
) -> None:
    """Test setting max power preserves the current mode and enabled state."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control.return_value = demand_control
    zone_device.set_demand_control = AsyncMock()
    await async_setup_daikin(hass, zone_device)
    entity_id = _demand_control_number_entity_id(entity_registry, zone_device.mac)
    assert entity_id is not None

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            CommonServiceArgument.ENTITY_ID: entity_id,
            NumberServiceArgument.VALUE: 75.0,
        },
        blocking=True,
    )

    zone_device.set_demand_control.assert_awaited_once_with(
        en_demand=expected_enabled,
        max_pow=75,
        mode=expected_mode,
    )


async def test_set_demand_control_max_power_invalid_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Reject a max power write when the device mode cannot be preserved."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control.return_value = {"en_demand": "invalid"}
    zone_device.set_demand_control = AsyncMock()
    await async_setup_daikin(hass, zone_device)
    entity_id = _demand_control_number_entity_id(entity_registry, zone_device.mac)
    assert entity_id is not None

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            NumberService.SET_VALUE,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                NumberServiceArgument.VALUE: 75.0,
            },
            blocking=True,
        )

    assert err.value.translation_key == "demand_control_invalid_state"
    zone_device.set_demand_control.assert_not_awaited()
