"""Test the Whirlpool select domain."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion
import whirlpool

from homeassistant.components.select import ATTR_OPTION, DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import init_integration, snapshot_whirlpool_entities, trigger_attr_callback


async def test_all_entities(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Test all entities."""
    await init_integration(hass)
    snapshot_whirlpool_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize(
    (
        "entity_id",
        "mock_fixture",
        "mock_getter_method_name",
        "mock_setter_method_name",
        "values",
    ),
    [
        (
            "select.beer_fridge_temperature_level",
            "mock_refrigerator_api",
            "get_offset_temp",
            "set_offset_temp",
            [(-4, "-4"), (-2, "-2"), (0, "0"), (3, "3"), (5, "5")],
        ),
    ],
)
async def test_select_entities(
    hass: HomeAssistant,
    entity_id: str,
    mock_fixture: str,
    mock_getter_method_name: str,
    mock_setter_method_name: str,
    values: list[tuple[int, str]],
    request: pytest.FixtureRequest,
) -> None:
    """Test reading and setting select options."""
    await init_integration(hass)
    mock_instance = request.getfixturevalue(mock_fixture)

    # Test reading current option
    mock_getter_method = getattr(mock_instance, mock_getter_method_name)
    for raw_value, expected_state in values:
        mock_getter_method.return_value = raw_value

        await trigger_attr_callback(hass, mock_instance)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state

    # Test changing option
    mock_setter_method = getattr(mock_instance, mock_setter_method_name)
    for raw_value, selected_option in values:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: selected_option},
            blocking=True,
        )
        assert mock_setter_method.call_count == 1
        mock_setter_method.assert_called_with(raw_value)
        mock_setter_method.reset_mock()


async def test_select_option_value_error(
    hass: HomeAssistant, mock_refrigerator_api: MagicMock
) -> None:
    """Test handling of ValueError exception when selecting an option."""
    await init_integration(hass)
    mock_refrigerator_api.set_offset_temp.side_effect = ValueError

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.beer_fridge_temperature_level",
                ATTR_OPTION: "something",
            },
            blocking=True,
        )


@pytest.fixture(
    params=[
        (
            "select.single_cavity_oven_cook_mode",
            "mock_oven_single_cavity_api",
            whirlpool.oven.Cavity.Upper,
        ),
        (
            "select.dual_cavity_oven_upper_oven_cook_mode",
            "mock_oven_dual_cavity_api",
            whirlpool.oven.Cavity.Upper,
        ),
        (
            "select.dual_cavity_oven_lower_oven_cook_mode",
            "mock_oven_dual_cavity_api",
            whirlpool.oven.Cavity.Lower,
        ),
    ]
)
def oven_cook_mode_entity(
    request: pytest.FixtureRequest,
) -> tuple[str, str, whirlpool.oven.Cavity]:
    """Parametrize the oven cook-mode select entities."""
    return request.param


async def test_oven_cook_mode_current(
    hass: HomeAssistant,
    oven_cook_mode_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test reading the current cook mode."""
    entity_id, mock_fixture, _ = oven_cook_mode_entity
    mock = request.getfixturevalue(mock_fixture)
    await init_integration(hass)

    assert hass.states.get(entity_id).state == "bake"
    mock.get_cook_mode.return_value = whirlpool.oven.CookMode.Broil
    await trigger_attr_callback(hass, mock)
    assert hass.states.get(entity_id).state == "broil"


async def test_oven_cook_mode_select(
    hass: HomeAssistant,
    oven_cook_mode_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test selecting a cook mode issues a cook command."""
    entity_id, mock_fixture, cavity = oven_cook_mode_entity
    mock = request.getfixturevalue(mock_fixture)
    await init_integration(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "broil"},
        blocking=True,
    )
    mock.set_cook.assert_called_once_with(
        target_temp=200, mode=whirlpool.oven.CookMode.Broil, cavity=cavity
    )


async def test_oven_cook_mode_select_from_idle(
    hass: HomeAssistant,
    oven_cook_mode_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test selecting a mode with no target set uses the default temperature."""
    entity_id, mock_fixture, cavity = oven_cook_mode_entity
    mock = request.getfixturevalue(mock_fixture)
    mock.get_target_temp.return_value = None
    await init_integration(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "broil"},
        blocking=True,
    )
    mock.set_cook.assert_called_once_with(
        target_temp=175, mode=whirlpool.oven.CookMode.Broil, cavity=cavity
    )


async def test_oven_cook_mode_select_standby(
    hass: HomeAssistant,
    oven_cook_mode_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test selecting standby stops the cook instead of starting one."""
    entity_id, mock_fixture, cavity = oven_cook_mode_entity
    mock = request.getfixturevalue(mock_fixture)
    await init_integration(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "standby"},
        blocking=True,
    )
    mock.stop_cook.assert_called_once_with(cavity)
    mock.set_cook.assert_not_called()


async def test_oven_cook_mode_select_value_error(
    hass: HomeAssistant,
    oven_cook_mode_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
) -> None:
    """Test a ValueError while setting the cook mode raises ServiceValidationError."""
    entity_id, mock_fixture, _ = oven_cook_mode_entity
    mock = request.getfixturevalue(mock_fixture)
    mock.set_cook.side_effect = ValueError
    await init_integration(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "broil"},
            blocking=True,
        )
