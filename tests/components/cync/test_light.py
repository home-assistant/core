"""Tests for the Cync integration light platform."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

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

    assert hass.states.get("light.lamp_bulb_1").state == "off"

    entity_id_parameter = {"entity_id": "light.lamp_bulb_1"}
    action_parameters = entity_id_parameter | input_parameters

    test_device = mock_config_entry.runtime_data.data.get(1111)
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
