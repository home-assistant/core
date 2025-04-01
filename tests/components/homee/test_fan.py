"""Test Homee fans."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_DECREASE_SPEED,
    SERVICE_INCREASE_SPEED,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("service", "options", "expected"),
    [
        (SERVICE_TURN_ON, {ATTR_PERCENTAGE: 100}, (77, 1, 8)),
        (SERVICE_TURN_ON, {ATTR_PERCENTAGE: 86}, (77, 1, 7)),
        (SERVICE_TURN_ON, {ATTR_PERCENTAGE: 63}, (77, 1, 6)),
        (SERVICE_TURN_ON, {ATTR_PERCENTAGE: 60}, (77, 1, 5)),
        (SERVICE_TURN_ON, {ATTR_PERCENTAGE: 50}, (77, 1, 4)),
        (SERVICE_TURN_ON, {ATTR_PERCENTAGE: 34}, (77, 1, 3)),
        (SERVICE_TURN_ON, {ATTR_PERCENTAGE: 17}, (77, 1, 2)),
        (SERVICE_TURN_ON, {ATTR_PERCENTAGE: 8}, (77, 1, 1)),
        (SERVICE_TURN_OFF, {}, (77, 1, 0)),
        (SERVICE_INCREASE_SPEED, {}, (77, 1, 4)),
        (SERVICE_DECREASE_SPEED, {}, (77, 1, 2)),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 42}, (77, 1, 4)),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "manual"}, (77, 2, 0)),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "auto"}, (77, 2, 1)),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "summer"}, (77, 2, 2)),
        (SERVICE_TOGGLE, {}, (77, 1, 0)),
    ],
)
async def test_fan_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    service: str,
    options: int | None,
    expected: tuple[int, int, int],
) -> None:
    """Test fan services."""
    mock_homee.nodes = [build_mock_node("fan.json")]
    await setup_integration(hass, mock_config_entry)

    OPTIONS = {ATTR_ENTITY_ID: "fan.test_fan"}
    OPTIONS.update(options)

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        OPTIONS,
        blocking=True,
    )

    mock_homee.set_value.assert_called_once_with(
        expected[0],
        expected[1],
        expected[2],  # type: ignore[arg-type]
    )
