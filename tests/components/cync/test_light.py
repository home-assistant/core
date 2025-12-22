"""Tests for the Cync integration light platform."""

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
    ("brightness_percentage", "color_temp_kelvin", "rgb"),
    [
        (100, 2500, None),
        (100, None, (50, 100, 150)),
        (None, 2500, None),
        (None, None, (50, 100, 150)),
    ],
)
async def test_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    brightness_percentage: int | None,
    color_temp_kelvin: int | None,
    rgb: tuple[int, int, int] | None,
) -> None:
    """Test that turning on the light changes all necessary attributes."""

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.lamp_bulb_1").state == "off"

    action_parameters = {
        "entity_id": "light.lamp_bulb_1",
        "brightness_pct": brightness_percentage,
        "color_temp_kelvin": color_temp_kelvin,
        "rgb_color": rgb,
    }
    action_parameters = {k: v for k, v in action_parameters.items() if v is not None}

    # now call the HA turn_on service
    await hass.services.async_call(
        "light",
        "turn_on",
        action_parameters,
        blocking=True,
    )

    changed_device = mock_config_entry.runtime_data.data.get(1111)

    expected_brightness = 90
    if brightness_percentage is not None:
        expected_brightness = brightness_percentage

    expected_kelvin = None
    if color_temp_kelvin is not None:
        min_kelvin = hass.states.get("light.lamp_bulb_1").attributes.get(
            "min_color_temp_kelvin", 2000
        )
        max_kelvin = hass.states.get("light.lamp_bulb_1").attributes.get(
            "max_color_temp_kelvin", 7000
        )
        expected_kelvin = _normalize_color_temp(
            min_kelvin, max_kelvin, color_temp_kelvin
        )

    if expected_kelvin is not None:
        expected_rgb = None
    elif rgb is not None:
        expected_rgb = rgb
    else:
        expected_rgb = (120, 145, 180)

    changed_device.set_combo.assert_called_once_with(
        changed_device, True, expected_brightness, expected_kelvin, expected_rgb
    )


def _normalize_color_temp(
    min_kelvin: float, max_kelvin: float, color_temp_kelvin: float | None
) -> int | None:
    """Return calculated color temp value scaled between 1-100."""
    if color_temp_kelvin is not None:
        kelvin_range = max_kelvin - min_kelvin
        scaled_kelvin = int(((color_temp_kelvin - min_kelvin) / kelvin_range) * 100)
        if scaled_kelvin == 0:
            scaled_kelvin += 1

        return scaled_kelvin
    return None
