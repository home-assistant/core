"""Test Homee fans."""

from unittest.mock import MagicMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion

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
from homeassistant.components.homee.const import (
    DOMAIN,
    PRESET_AUTO,
    PRESET_MANUAL,
    PRESET_SUMMER,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("speed", "expected"),
    [
        (0, 0),
        (1, 12),
        (2, 25),
        (3, 37),
        (4, 50),
        (5, 62),
        (6, 75),
        (7, 87),
        (8, 100),
    ],
)
async def test_percentage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    speed: int,
    expected: int,
) -> None:
    """Test percentage."""
    mock_homee.nodes = [build_mock_node("fan.json")]
    mock_homee.nodes[0].attributes[0].current_value = speed
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("fan.test_fan").attributes["percentage"] == expected


@pytest.mark.parametrize(
    ("mode_value", "expected"),
    [
        (0, "manual"),
        (1, "auto"),
        (2, "summer"),
    ],
)
async def test_preset_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    mode_value: int,
    expected: str,
) -> None:
    """Test preset mode."""
    mock_homee.nodes = [build_mock_node("fan.json")]
    mock_homee.nodes[0].attributes[1].current_value = mode_value
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("fan.test_fan").attributes["preset_mode"] == expected


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
        (SERVICE_TURN_ON, {}, (77, 1, 6)),
        (SERVICE_TURN_OFF, {}, (77, 1, 0)),
        (SERVICE_INCREASE_SPEED, {}, (77, 1, 4)),
        (SERVICE_DECREASE_SPEED, {}, (77, 1, 2)),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 42}, (77, 1, 4)),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_MANUAL}, (77, 2, 0)),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_AUTO}, (77, 2, 1)),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_SUMMER}, (77, 2, 2)),
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

    mock_homee.set_value.assert_called_once_with(*expected)


async def test_turn_on_preset_last_value_zero(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
) -> None:
    """Test turn on with preset last value == 0."""
    mock_homee.nodes = [build_mock_node("fan.json")]
    mock_homee.nodes[0].attributes[0].last_value = 0
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_fan", ATTR_PRESET_MODE: PRESET_MANUAL},
        blocking=True,
    )

    assert mock_homee.set_value.call_args_list == [
        call(77, 2, 0),
        call(77, 1, 8),
    ]


async def test_turn_on_invalid_preset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
) -> None:
    """Test turn on with invalid preset."""
    mock_homee.nodes = [build_mock_node("fan.json")]
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "fan.test_fan", ATTR_PRESET_MODE: PRESET_AUTO},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_preset_mode"


async def test_fan_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the fan snapshot."""
    mock_homee.nodes = [build_mock_node("fan.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
