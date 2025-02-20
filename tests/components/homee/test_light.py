"""Test homee lights."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


def mock_attribute_map(attributes) -> dict:
    """Mock the attribute map of a Homee node."""
    attribute_map = {}
    for a in attributes:
        attribute_map[a.type] = a

    return attribute_map


async def setup_mock_light(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    file: str,
) -> None:
    """Setups the light node for the tests."""
    mock_homee.nodes = [build_mock_node(file)]
    mock_homee.nodes[0].attribute_map = mock_attribute_map(
        mock_homee.nodes[0].attributes
    )
    await setup_integration(hass, mock_config_entry)


async def test_turn_on(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the light."""
    await setup_mock_light(hass, mock_homee, mock_config_entry, "lights.json")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_light_light_1"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, 1)
    mock_homee.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_light_light_1", ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 2, 100)
    mock_homee.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_TEMP_KELVIN: 4300,
        },
        blocking=True,
    )

    calls = mock_homee.set_value.call_args_list
    assert calls[0][0] == (1, 2, 100)
    assert calls[1][0] == (1, 4, 4300)
    mock_homee.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
            ATTR_HS_COLOR: (100, 100),
        },
        blocking=True,
    )

    calls = mock_homee.set_value.call_args_list
    assert calls[0][0] == (1, 1, 1)
    assert calls[1][0] == (1, 3, 5635840)


async def test_turn_off(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a light."""
    await setup_mock_light(hass, mock_homee, mock_config_entry, "lights.json")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
        },
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, 0)


async def test_toggle(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test toggling a light."""
    await setup_mock_light(hass, mock_homee, mock_config_entry, "lights.json")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TOGGLE,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
        },
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, 0)

    mock_homee.nodes[0].attributes[0].current_value = 0.0
    mock_homee.nodes[0].add_on_changed_listener.call_args_list[0][0][0](
        mock_homee.nodes[0]
    )
    await hass.async_block_till_done()
    mock_homee.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TOGGLE,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
        },
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, 1)


async def test_light_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test snapshot of lights."""
    mock_homee.nodes = [
        build_mock_node("lights.json"),
        build_mock_node("light_single.json"),
    ]
    for i in range(2):
        mock_homee.nodes[i].attribute_map = mock_attribute_map(
            mock_homee.nodes[i].attributes
        )
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
