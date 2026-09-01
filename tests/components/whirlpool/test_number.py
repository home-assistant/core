"""Test the Whirlpool number platform."""

import pytest
from syrupy.assertion import SnapshotAssertion
import whirlpool

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import init_integration, snapshot_whirlpool_entities, trigger_attr_callback


@pytest.fixture(
    params=[
        (
            "number.single_cavity_oven_target_temperature",
            "mock_oven_single_cavity_api",
            whirlpool.oven.Cavity.Upper,
        ),
        (
            "number.dual_cavity_oven_upper_oven_target_temperature",
            "mock_oven_dual_cavity_api",
            whirlpool.oven.Cavity.Upper,
        ),
        (
            "number.dual_cavity_oven_lower_oven_target_temperature",
            "mock_oven_dual_cavity_api",
            whirlpool.oven.Cavity.Lower,
        ),
    ]
)
def oven_number_entity(
    request: pytest.FixtureRequest,
) -> tuple[str, str, whirlpool.oven.Cavity]:
    """Parametrize the oven target-temperature number entities."""
    return request.param


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Test all entities."""
    await init_integration(hass)
    snapshot_whirlpool_entities(hass, entity_registry, snapshot, Platform.NUMBER)


async def test_target_temperature_value(
    hass: HomeAssistant,
    oven_number_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test reading and updating the target temperature."""
    entity_id, mock_fixture, _ = oven_number_entity
    mock = request.getfixturevalue(mock_fixture)
    await init_integration(hass)

    assert hass.states.get(entity_id).state == "200"

    mock.get_target_temp.return_value = 220
    await trigger_attr_callback(hass, mock)
    assert hass.states.get(entity_id).state == "220"


async def test_set_target_temperature(
    hass: HomeAssistant,
    oven_number_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test setting the target temperature issues a cook command."""
    entity_id, mock_fixture, cavity = oven_number_entity
    mock = request.getfixturevalue(mock_fixture)
    mock.get_cook_mode.return_value = whirlpool.oven.CookMode.Broil
    await init_integration(hass)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 220},
        blocking=True,
    )
    mock.set_cook.assert_called_once_with(
        target_temp=220, mode=whirlpool.oven.CookMode.Broil, cavity=cavity
    )


async def test_set_fractional_target_temperature(
    hass: HomeAssistant,
    oven_number_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test a fractional target temperature is passed through without truncation."""
    entity_id, mock_fixture, cavity = oven_number_entity
    mock = request.getfixturevalue(mock_fixture)
    mock.get_cook_mode.return_value = whirlpool.oven.CookMode.Broil
    await init_integration(hass)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 220.5},
        blocking=True,
    )
    mock.set_cook.assert_called_once_with(
        target_temp=220.5, mode=whirlpool.oven.CookMode.Broil, cavity=cavity
    )


async def test_set_target_temperature_failure(
    hass: HomeAssistant,
    oven_number_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test a failed request raises HomeAssistantError."""
    entity_id, mock_fixture, _ = oven_number_entity
    mock = request.getfixturevalue(mock_fixture)
    mock.set_cook.return_value = False
    await init_integration(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 220},
            blocking=True,
        )


async def test_set_target_temperature_value_error(
    hass: HomeAssistant,
    oven_number_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test a ValueError while setting the temperature raises ServiceValidationError."""
    entity_id, mock_fixture, _ = oven_number_entity
    mock = request.getfixturevalue(mock_fixture)
    mock.set_cook.side_effect = ValueError
    await init_integration(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 220},
            blocking=True,
        )


@pytest.mark.parametrize("current_mode", [whirlpool.oven.CookMode.Standby, None])
async def test_set_target_temperature_from_idle(
    hass: HomeAssistant,
    oven_number_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
    current_mode: whirlpool.oven.CookMode | None,
) -> None:
    """Test that setting the temperature with no active cook defaults to Bake."""
    entity_id, mock_fixture, cavity = oven_number_entity
    mock = request.getfixturevalue(mock_fixture)
    mock.get_cook_mode.return_value = current_mode
    await init_integration(hass)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 220},
        blocking=True,
    )
    mock.set_cook.assert_called_once_with(
        target_temp=220, mode=whirlpool.oven.CookMode.Bake, cavity=cavity
    )
