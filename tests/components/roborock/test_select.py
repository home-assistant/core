"""Test Roborock Select platform."""

from typing import Any
from unittest.mock import AsyncMock, Mock, call

import pytest
from roborock import CleanTypeMapping, RoborockCommand
from roborock.data import (
    RoborockDockDustCollectionModeCode,
    WaterLevelMapping,
    ZeoProgram,
)
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockZeoProtocol

from homeassistant.components.roborock import DOMAIN
from homeassistant.components.roborock.select import (
    A01_SELECT_DESCRIPTIONS,
    RoborockSelectEntityA01,
)
from homeassistant.const import SERVICE_SELECT_OPTION, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
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


@pytest.fixture
def q7_device(fake_devices: list[FakeDevice]) -> FakeDevice:
    """Get the fake Q7 vacuum device."""
    # The Q7 is the fourth device in the list (index 3) based on HOME_DATA
    return fake_devices[3]


async def test_update_success_q7_water_level(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    q7_device: FakeDevice,
) -> None:
    """Test allowed changing values for Q7 water flow select entity."""
    entity_id = "select.roborock_q7_water_flow"
    assert hass.states.get(entity_id) is not None

    # Test setting value
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        service_data={"option": "high"},
        blocking=True,
        target={"entity_id": entity_id},
    )

    assert q7_device.b01_q7_properties
    assert q7_device.b01_q7_properties.set_water_level.call_count == 1
    q7_device.b01_q7_properties.set_water_level.assert_called_with(
        WaterLevelMapping.HIGH
    )


async def test_update_failure_q7_water_level(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    q7_device: FakeDevice,
) -> None:
    """Test failure when setting Q7 water flow."""
    assert q7_device.b01_q7_properties
    q7_device.b01_q7_properties.set_water_level.side_effect = RoborockException
    entity_id = "select.roborock_q7_water_flow"
    assert hass.states.get(entity_id) is not None

    with pytest.raises(HomeAssistantError, match="Error while calling water_flow"):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": "high"},
            blocking=True,
            target={"entity_id": entity_id},
        )


async def test_update_failure_q7_cleaning_mode(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    q7_device: FakeDevice,
) -> None:
    """Test failure when setting Q7 cleaning mode."""
    assert q7_device.b01_q7_properties
    q7_device.b01_q7_properties.set_mode.side_effect = RoborockException

    with pytest.raises(HomeAssistantError, match="Error while calling cleaning_mode"):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": "vacuum"},
            blocking=True,
            target={"entity_id": "select.roborock_q7_cleaning_mode"},
        )


async def test_update_success_q7_cleaning_mode(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    q7_device: FakeDevice,
) -> None:
    """Test allowed changing values for Q7 cleaning mode select entity."""
    entity_id = "select.roborock_q7_cleaning_mode"
    assert hass.states.get(entity_id) is not None

    # Test setting value
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        service_data={"option": "vacuum"},
        blocking=True,
        target={"entity_id": entity_id},
    )

    assert q7_device.b01_q7_properties
    assert q7_device.b01_q7_properties.set_mode.call_count == 1

    q7_device.b01_q7_properties.set_mode.assert_called_with(CleanTypeMapping.VACUUM)


@pytest.fixture
def zeo_device(fake_devices: list[FakeDevice]) -> FakeDevice:
    """Get the fake Zeo washing machine device."""
    return next(device for device in fake_devices if getattr(device, "zeo", None))


async def test_update_success_zeo_program(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    zeo_device: FakeDevice,
) -> None:
    """Test changing values for A01 Zeo select entities."""
    option = ZeoProgram.keys()[0]
    entity_id = entity_registry.async_get_entity_id(
        "select", DOMAIN, "program_zeo_duid"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None

    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        service_data={"option": option},
        blocking=True,
        target={"entity_id": entity_id},
    )

    assert zeo_device.zeo
    zeo_device.zeo.set_value.assert_awaited_once_with(
        RoborockZeoProtocol.PROGRAM,
        ZeoProgram.as_dict()[option],
    )


async def test_current_option_zeo_program() -> None:
    """Test current option retrieval for A01 Zeo select entities."""
    coordinator = Mock(
        duid_slug="zeo_duid",
        device_info=Mock(),
        data={RoborockZeoProtocol.PROGRAM: 1},
        api=AsyncMock(),
        async_request_refresh=AsyncMock(),
    )
    entity = RoborockSelectEntityA01(coordinator, A01_SELECT_DESCRIPTIONS[0])

    assert entity.current_option == "1"
    coordinator.data = {}
    assert entity.current_option is None
    coordinator.data = {RoborockZeoProtocol.PROGRAM: None}
    assert entity.current_option is None


async def test_update_failure_zeo_program(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    zeo_device: FakeDevice,
) -> None:
    """Test failure while setting an A01 Zeo select option."""
    assert zeo_device.zeo
    zeo_device.zeo.set_value.side_effect = RoborockException
    option = ZeoProgram.keys()[0]
    entity_id = entity_registry.async_get_entity_id(
        "select", DOMAIN, "program_zeo_duid"
    )
    assert entity_id is not None

    with pytest.raises(HomeAssistantError, match="Error while calling program"):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": option},
            blocking=True,
            target={"entity_id": entity_id},
        )


async def test_update_failure_zeo_invalid_option() -> None:
    """Test invalid option handling in A01 select entity."""
    coordinator = Mock(
        duid_slug="zeo_duid",
        device_info=Mock(),
        data={},
        api=AsyncMock(),
        async_request_refresh=AsyncMock(),
    )
    entity = RoborockSelectEntityA01(coordinator, A01_SELECT_DESCRIPTIONS[0])

    with pytest.raises(ServiceValidationError):
        await entity.async_select_option("invalid_option")

    coordinator.api.set_value.assert_not_called()
