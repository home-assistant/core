"""Test the Whirlpool select domain."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

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
