"""Tests for the Cync integration light platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that light attributes are properly set on setup."""

    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("input_parameters", "expected_brightness", "expected_color_temp", "expected_rgb"),
    [
        ({"brightness_pct": 100, "color_temp_kelvin": 2500}, 100, 10, None),
        (
            {"brightness_pct": 100, "rgb_color": (50, 100, 150)},
            100,
            None,
            (50, 100, 150),
        ),
        ({"color_temp_kelvin": 2500}, 90, 10, None),
        ({"rgb_color": (50, 100, 150)}, 90, None, (50, 100, 150)),
    ],
)
async def test_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    input_parameters: dict,
    expected_brightness: int | None,
    expected_color_temp: int | None,
    expected_rgb: tuple[int, int, int] | None,
) -> None:
    """Test that turning on the light changes all necessary attributes."""

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.office_lamp_bulb_1").state == "off"

    entity_id_parameter = {"entity_id": "light.office_lamp_bulb_1"}
    action_parameters = entity_id_parameter | input_parameters

    test_device = mock_config_entry.runtime_data.data["1000-2"]
    test_device.set_combo = AsyncMock(name="set_combo")

    # now call the HA turn_on service
    await hass.services.async_call(
        "light",
        "turn_on",
        action_parameters,
        blocking=True,
    )

    test_device.set_combo.assert_called_once_with(
        True, expected_brightness, expected_color_temp, expected_rgb
    )


@pytest.mark.parametrize(
    ("unique_id", "mesh_unique_id"),
    [
        pytest.param("1000-1101", "1000-1", id="room-light"),
        pytest.param("1000-1111", "1000-2", id="group-light"),
        pytest.param("1000-1112", "1000-3", id="initially-offline-light"),
    ],
)
@pytest.mark.parametrize(
    ("is_online", "expected_state"),
    [
        pytest.param(True, STATE_ON, id="online"),
        pytest.param(False, STATE_UNAVAILABLE, id="offline"),
    ],
)
async def test_mesh_state_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    cync_client: MagicMock,
    unique_id: str,
    mesh_unique_id: str,
    is_online: bool,
    expected_state: str,
) -> None:
    """Test mesh callbacks update lights with legacy registry identifiers."""
    await setup_integration(hass, mock_config_entry)
    home = cync_client.get_homes.return_value[0]
    updated_light = deepcopy(
        next(
            device
            for device in home.get_flattened_device_list()
            if device.unique_id == mesh_unique_id
        )
    )
    updated_light.update_state(True, 50, 254, (100, 150, 200), is_online)
    callback = cync_client.set_update_callback.call_args.args[0]

    await callback({mesh_unique_id: updated_light})
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(Platform.LIGHT, "cync", unique_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert mock_config_entry.runtime_data.data[mesh_unique_id] is updated_light
    assert set(mock_config_entry.runtime_data.data) == {
        "1000-1",
        "1000-2",
        mesh_unique_id,
    }
