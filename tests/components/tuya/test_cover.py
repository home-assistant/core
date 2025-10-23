"""Test Tuya cover platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_zah67ekd"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_open_service(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test open service."""
    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "control", "value": "open"},
            {"code": "percent_control", "value": 0},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_zah67ekd"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_close_service(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test close service."""
    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "control", "value": "close"},
            {"code": "percent_control", "value": 100},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_zah67ekd"],
)
async def test_set_position(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set position service (not available on this device)."""
    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_POSITION: 25,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "percent_control", "value": 75},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_zah67ekd"],
)
@pytest.mark.parametrize(
    ("percent_control", "percent_state"),
    [
        (100, 52),
        (0, 100),
        (50, 25),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_percent_state_on_cover(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    percent_control: int,
    percent_state: int,
) -> None:
    """Test percent_state attribute on the cover entity."""
    mock_device.status["percent_control"] = percent_control
    # 100 is closed and 0 is open for Tuya covers
    mock_device.status["percent_state"] = 100 - percent_state

    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.attributes[ATTR_CURRENT_POSITION] == percent_state


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_zah67ekd"],
)
async def test_set_tilt_position_not_supported(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set tilt position service (not available on this device)."""
    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TILT_POSITION: 50,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "mock_device_code",
    ["clkg_wltqkykhni0papzj"],
)
@pytest.mark.parametrize(
    ("initial_percent_control", "expected_state", "expected_position"),
    [
        (0, "closed", 0),
        (25, "open", 25),
        (50, "open", 50),
        (75, "open", 75),
        (100, "open", 100),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_clkg_wltqkykhni0papzj_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    initial_percent_control: int,
    expected_state: str,
    expected_position: int,
) -> None:
    """Test cover position for wltqkykhni0papzj device.

    See https://github.com/home-assistant/core/issues/151635
    percent_control == 0 is when my roller shutter is completely open (meaning up)
    percent_control == 100 is when my roller shutter is completely closed (meaning down)
    """
    entity_id = "cover.roller_shutter_living_room_curtain"
    mock_device.status["percent_control"] = initial_percent_control

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.state == expected_state
    assert state.attributes[ATTR_CURRENT_POSITION] == expected_position


@pytest.mark.parametrize(
    "mock_device_code",
    ["clkg_wltqkykhni0papzj"],
)
@pytest.mark.parametrize(
    ("service_name", "service_kwargs", "expected_commands"),
    [
        (
            SERVICE_OPEN_COVER,
            {},
            [
                {"code": "control", "value": "open"},
                {"code": "percent_control", "value": 100},
            ],
        ),
        (
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 25},
            [
                {"code": "percent_control", "value": 25},
            ],
        ),
        (
            SERVICE_CLOSE_COVER,
            {},
            [
                {"code": "control", "value": "close"},
                {"code": "percent_control", "value": 0},
            ],
        ),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_clkg_wltqkykhni0papzj_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service_name: str,
    service_kwargs: dict,
    expected_commands: list[dict],
) -> None:
    """Test cover position for wltqkykhni0papzj device.

    See https://github.com/home-assistant/core/issues/151635
    percent_control == 0 is when my roller shutter is completely open (meaning up)
    percent_control == 100 is when my roller shutter is completely closed (meaning down)
    """
    entity_id = "cover.roller_shutter_living_room_curtain"
    mock_device.status["percent_control"] = 50

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        COVER_DOMAIN,
        service_name,
        {ATTR_ENTITY_ID: entity_id, **service_kwargs},
        blocking=True,
    )

    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        expected_commands,
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_n3xgr5pdmpinictg"],
)
@pytest.mark.parametrize(
    ("initial_control", "expected_state"),
    [
        ("open", STATE_OPEN),
        ("stop", STATE_UNKNOWN),
        ("close", STATE_CLOSED),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_cl_n3xgr5pdmpinictg_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    initial_control: str,
    expected_state: str,
) -> None:
    """Test cover position for n3xgr5pdmpinictg device.

    See https://github.com/home-assistant/core/issues/153537
    """
    entity_id = "cover.estore_sala_curtain"
    mock_device.status["control"] = initial_control

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.state == expected_state
