"""Tests for the Cync integration switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

PLUG_UNIQUE_ID = "10000-4"
PLUG_ENTITY_ID = "switch.bedroom_bedroom_plug"
DUAL_OUTLET_DEVICE_ID = 1401
DUAL_OUTLET_LEFT_UNIQUE_ID = "10000-1006"
DUAL_OUTLET_RIGHT_UNIQUE_ID = "10000-2006"


@pytest.fixture(autouse=True)
def switch_platform_only():
    """Limit platform setup to switch only."""
    with patch("homeassistant.components.cync._PLATFORMS", [Platform.SWITCH]):
        yield


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that switch attributes are properly set on setup."""

    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_dual_outlet_devices_are_independently_addressable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test outlets sharing a cloud device ID use distinct mesh IDs."""
    await setup_integration(hass, mock_config_entry)

    left_entry = entity_registry.async_get_entity_id(
        Platform.SWITCH, "cync", DUAL_OUTLET_LEFT_UNIQUE_ID
    )
    right_entry = entity_registry.async_get_entity_id(
        Platform.SWITCH, "cync", DUAL_OUTLET_RIGHT_UNIQUE_ID
    )

    assert left_entry is not None
    assert right_entry is not None
    assert left_entry != right_entry
    assert (
        len(
            [
                device
                for device in mock_config_entry.runtime_data.data.values()
                if device.device_id == DUAL_OUTLET_DEVICE_ID
            ]
        )
        == 2
    )
    await mock_config_entry.runtime_data.on_data_update(
        {
            DUAL_OUTLET_LEFT_UNIQUE_ID: mock_config_entry.runtime_data.data[
                DUAL_OUTLET_LEFT_UNIQUE_ID
            ],
            DUAL_OUTLET_RIGHT_UNIQUE_ID: mock_config_entry.runtime_data.data[
                DUAL_OUTLET_RIGHT_UNIQUE_ID
            ],
        }
    )
    left_state = hass.states.get(left_entry)
    right_state = hass.states.get(right_entry)
    assert left_state is not None
    assert right_state is not None
    assert left_state.state == "on"
    assert right_state.state == "off"


async def test_dual_outlet_control_targets_selected_outlet(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test controlling one outlet does not control its sibling."""
    await setup_integration(hass, mock_config_entry)

    left_entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, "cync", DUAL_OUTLET_LEFT_UNIQUE_ID
    )
    left_device = mock_config_entry.runtime_data.data[DUAL_OUTLET_LEFT_UNIQUE_ID]
    right_device = mock_config_entry.runtime_data.data[DUAL_OUTLET_RIGHT_UNIQUE_ID]
    left_device.turn_off = AsyncMock(name="left_turn_off")
    right_device.turn_off = AsyncMock(name="right_turn_off")

    assert left_entity_id is not None
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": left_entity_id},
        blocking=True,
    )

    left_device.turn_off.assert_awaited_once_with()
    right_device.turn_off.assert_not_awaited()


async def test_initial_state_is_unknown_until_device_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test plug state remains unknown until pycync reports its state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(PLUG_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"

    device = mock_config_entry.runtime_data.data[PLUG_UNIQUE_ID]
    device.update_state(True)
    await mock_config_entry.runtime_data.on_data_update({PLUG_UNIQUE_ID: device})

    state = hass.states.get(PLUG_ENTITY_ID)
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    ("service", "device_method", "other_method"),
    [
        ("turn_on", "turn_on", "turn_off"),
        ("turn_off", "turn_off", "turn_on"),
    ],
    ids=["turn_on", "turn_off"],
)
async def test_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service: str,
    device_method: str,
    other_method: str,
) -> None:
    """Test that turning on/off the plug calls the device on/off methods."""

    await setup_integration(hass, mock_config_entry)

    test_device = mock_config_entry.runtime_data.data.get(PLUG_UNIQUE_ID)
    test_device.turn_on = AsyncMock(name="turn_on")
    test_device.turn_off = AsyncMock(name="turn_off")

    await hass.services.async_call(
        "switch",
        service,
        {"entity_id": PLUG_ENTITY_ID},
        blocking=True,
    )

    getattr(test_device, device_method).assert_awaited_once()
    getattr(test_device, other_method).assert_not_awaited()
