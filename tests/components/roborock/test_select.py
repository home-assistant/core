"""Test Roborock Select platform."""

from typing import Any
from unittest.mock import AsyncMock, call

import pytest
from roborock import RoborockCommand
from roborock.data.v1 import RoborockDockDustCollectionModeCode
from roborock.exceptions import RoborockException

from homeassistant.components.roborock import DOMAIN
from homeassistant.const import SERVICE_SELECT_OPTION, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .conftest import FakeDevice

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SELECT]


@pytest.mark.parametrize(
    ("entity_id", "value", "expected_command", "expected_params"),
    [
        (
            "select.roborock_s7_maxv_mop_mode",
            "deep",
            RoborockCommand.SET_MOP_MODE,
            [301],
        ),
        (
            "select.roborock_s7_maxv_mop_intensity",
            "mild",
            RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
            [201],
        ),
    ],
)
async def test_update_success(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_id: str,
    value: str,
    expected_command: RoborockCommand,
    expected_params: Any,
    fake_vacuum: FakeDevice,
) -> None:
    """Test allowed changing values for select entities."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        service_data={"option": value},
        blocking=True,
        target={"entity_id": entity_id},
    )
    assert fake_vacuum.v1_properties
    assert fake_vacuum.v1_properties.command.send.call_count == 1
    assert fake_vacuum.v1_properties.command.send.call_args == (
        call(expected_command, params=expected_params)
    )


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("select.roborock_s7_maxv_selected_map", "Downstairs"),
    ],
)
async def test_update_success_selected_map(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_id: str,
    value: str,
    fake_vacuum: FakeDevice,
) -> None:
    """Test allowed changing values for select entities."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        service_data={"option": value},
        blocking=True,
        target={"entity_id": entity_id},
    )
    assert fake_vacuum.v1_properties
    assert fake_vacuum.v1_properties.maps.set_current_map.call_count == 1
    assert fake_vacuum.v1_properties.maps.set_current_map.call_args == [(1,)]


async def test_update_failure(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that changing a value will raise a homeassistanterror when it fails."""
    assert fake_vacuum.v1_properties
    fake_vacuum.v1_properties.command.send.side_effect = RoborockException

    with pytest.raises(HomeAssistantError, match="Error while calling SET_MOP_MOD"):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": "deep"},
            blocking=True,
            target={"entity_id": "select.roborock_s7_maxv_mop_mode"},
        )


async def test_none_map_select(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that the select entity correctly handles not having a current map."""
    # Set map status to None so that current map is never set
    fake_vacuum.v1_properties.home.current_map_data = None
    await async_setup_component(hass, DOMAIN, {})
    select_entity = hass.states.get("select.roborock_s7_maxv_selected_map")
    assert select_entity
    assert select_entity.state == STATE_UNKNOWN


async def test_selected_map_name(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test that the selected map is set to the correct map name."""
    await async_setup_component(hass, DOMAIN, {})
    select_entity = hass.states.get("select.roborock_s7_maxv_selected_map")
    assert select_entity.state == "Upstairs"


async def test_selected_map_without_name(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that maps without a name are given a placeholder name."""
    assert fake_vacuum.v1_properties
    assert fake_vacuum.v1_properties.home.home_map_info
    fake_vacuum.v1_properties.home.home_map_info[0].name = ""
    fake_vacuum.v1_properties.home.refresh = AsyncMock()

    await async_setup_component(hass, DOMAIN, {})

    select_entity = hass.states.get("select.roborock_s7_maxv_selected_map")
    assert select_entity
    assert select_entity.state == "Map 0"


@pytest.mark.parametrize(
    ("dust_collection_mode", "expected_state"),
    [
        (None, "unknown"),
        (RoborockDockDustCollectionModeCode.smart, "smart"),
        (RoborockDockDustCollectionModeCode.light, "light"),
    ],
)
async def test_dust_collection_mode_none(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    dust_collection_mode: RoborockDockDustCollectionModeCode | None,
    expected_state: str,
) -> None:
    """Test that the dust collection mode entity correctly handles mode values."""
    assert fake_vacuum.v1_properties
    assert fake_vacuum.v1_properties.dust_collection_mode
    fake_vacuum.v1_properties.dust_collection_mode.mode = dust_collection_mode

    await async_setup_component(hass, DOMAIN, {})

    select_entity = hass.states.get("select.roborock_s7_maxv_dock_empty_mode")
    assert select_entity
    assert select_entity.state == expected_state
