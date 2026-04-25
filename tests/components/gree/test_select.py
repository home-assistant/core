"""Tests for gree select entities."""

from unittest.mock import Mock, patch

from greeclimate.device import HorizontalSwing, VerticalSwing
from greeclimate.exceptions import DeviceTimeoutError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gree.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ENTITY_ID_HORIZONTAL_SWING = f"{SELECT_DOMAIN}.fake_device_1_horizontal_swing"
ENTITY_ID_VERTICAL_SWING = f"{SELECT_DOMAIN}.fake_device_1_vertical_swing"


async def async_setup_gree(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the gree select platform."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {SELECT_DOMAIN: {}}})
    await hass.async_block_till_done()
    return entry


@patch("homeassistant.components.gree.PLATFORMS", [SELECT_DOMAIN])
async def test_registry_settings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test entity registry settings."""
    entry = await async_setup_gree(hass)

    state = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert state == snapshot


@patch("homeassistant.components.gree.PLATFORMS", [SELECT_DOMAIN])
async def test_entity_state(
    hass: HomeAssistant,
    device: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test initial entity state matches snapshot."""
    device().horizontal_swing = HorizontalSwing.Default
    device().vertical_swing = VerticalSwing.Default

    await async_setup_gree(hass)

    state = hass.states.async_all(SELECT_DOMAIN)
    assert state == snapshot


@patch("homeassistant.components.gree.PLATFORMS", [SELECT_DOMAIN])
@pytest.mark.parametrize(
    "option",
    ["Default", "FullSwing", "Left", "LeftCenter", "Center", "RightCenter", "Right"],
)
async def test_send_horizontal_swing(
    hass: HomeAssistant, option: str
) -> None:
    """Test sending a horizontal swing option to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID_HORIZONTAL_SWING, ATTR_OPTION: option},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID_HORIZONTAL_SWING)
    assert state is not None
    assert state.state == option


@patch("homeassistant.components.gree.PLATFORMS", [SELECT_DOMAIN])
@pytest.mark.parametrize(
    "option",
    [
        "Default",
        "FullSwing",
        "FixedUpper",
        "FixedUpperMiddle",
        "FixedMiddle",
        "FixedLowerMiddle",
        "FixedLower",
        "SwingUpper",
        "SwingUpperMiddle",
        "SwingMiddle",
        "SwingLowerMiddle",
        "SwingLower",
    ],
)
async def test_send_vertical_swing(
    hass: HomeAssistant, option: str
) -> None:
    """Test sending a vertical swing option to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID_VERTICAL_SWING, ATTR_OPTION: option},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID_VERTICAL_SWING)
    assert state is not None
    assert state.state == option


@patch("homeassistant.components.gree.PLATFORMS", [SELECT_DOMAIN])
async def test_send_horizontal_swing_device_timeout(
    hass: HomeAssistant, device: Mock
) -> None:
    """Test horizontal swing option is applied optimistically on device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID_HORIZONTAL_SWING, ATTR_OPTION: "Left"},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID_HORIZONTAL_SWING)
    assert state is not None
    assert state.state == "Left"


@patch("homeassistant.components.gree.PLATFORMS", [SELECT_DOMAIN])
async def test_send_vertical_swing_device_timeout(
    hass: HomeAssistant, device: Mock
) -> None:
    """Test vertical swing option is applied optimistically on device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID_VERTICAL_SWING, ATTR_OPTION: "SwingMiddle"},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID_VERTICAL_SWING)
    assert state is not None
    assert state.state == "SwingMiddle"


@patch("homeassistant.components.gree.PLATFORMS", [SELECT_DOMAIN])
@pytest.mark.parametrize(
    "option",
    ["Default", "FullSwing", "Left", "LeftCenter", "Center", "RightCenter", "Right"],
)
async def test_update_horizontal_swing(
    hass: HomeAssistant, device: Mock, option: str
) -> None:
    """Test that entity state reflects device horizontal swing value."""
    device().horizontal_swing = HorizontalSwing[option]

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID_HORIZONTAL_SWING)
    assert state is not None
    assert state.state == option


@patch("homeassistant.components.gree.PLATFORMS", [SELECT_DOMAIN])
@pytest.mark.parametrize(
    "option",
    [
        "Default",
        "FullSwing",
        "FixedUpper",
        "FixedUpperMiddle",
        "FixedMiddle",
        "FixedLowerMiddle",
        "FixedLower",
        "SwingUpper",
        "SwingUpperMiddle",
        "SwingMiddle",
        "SwingLowerMiddle",
        "SwingLower",
    ],
)
async def test_update_vertical_swing(
    hass: HomeAssistant, device: Mock, option: str
) -> None:
    """Test that entity state reflects device vertical swing value."""
    device().vertical_swing = VerticalSwing[option]

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID_VERTICAL_SWING)
    assert state is not None
    assert state.state == option
