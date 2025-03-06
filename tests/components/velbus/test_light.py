"""Velbus light platform tests."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_FLASH,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    FLASH_LONG,
    FLASH_SHORT,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.LIGHT]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_dimmer_actions(
    hass: HomeAssistant,
    mock_dimmer: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test every supported dimmer action."""
    await init_integration(hass, config_entry)
    # turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.dimmer_full_name_dimmer"},
        blocking=True,
    )
    mock_dimmer.set_dimmer_state.assert_called_once_with(0, 0)
    # turn on without brightness == restore previous brightness
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.dimmer_full_name_dimmer", ATTR_TRANSITION: 1},
        blocking=True,
    )
    mock_dimmer.restore_dimmer_state.assert_called_once_with(1)
    # turn on with brightness == 0
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.dimmer_full_name_dimmer",
            ATTR_BRIGHTNESS: 0,
            ATTR_TRANSITION: 1,
        },
        blocking=True,
    )
    mock_dimmer.set_dimmer_state.assert_called_with(0, 1)
    assert mock_dimmer.set_dimmer_state.call_count == 2
    # turn on with brightness == 33
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.dimmer_full_name_dimmer", ATTR_BRIGHTNESS: 33},
        blocking=True,
    )
    mock_dimmer.set_dimmer_state.assert_called_with(12, 0)
    assert mock_dimmer.set_dimmer_state.call_count == 3


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_led_actions(
    hass: HomeAssistant,
    mock_button: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test every supported button led action."""
    await init_integration(hass, config_entry)
    # turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.bedroom_kid_1_led_buttonon"},
        blocking=True,
    )
    mock_button.set_led_state.assert_called_once_with("off")
    # turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.bedroom_kid_1_led_buttonon"},
        blocking=True,
    )
    mock_button.set_led_state.assert_called_with("on")
    assert mock_button.set_led_state.call_count == 2
    # turn on with FLASH_LONG
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.bedroom_kid_1_led_buttonon", ATTR_FLASH: FLASH_LONG},
        blocking=True,
    )
    mock_button.set_led_state.assert_called_with("slow")
    assert mock_button.set_led_state.call_count == 3
    # turn on with FLASH_SHORT
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.bedroom_kid_1_led_buttonon", ATTR_FLASH: FLASH_SHORT},
        blocking=True,
    )
    mock_button.set_led_state.assert_called_with("fast")
    assert mock_button.set_led_state.call_count == 4
    # turn on with UNKNOWN flash option
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.bedroom_kid_1_led_buttonon", ATTR_FLASH: FLASH_SHORT},
        blocking=True,
    )
    mock_button.set_led_state.assert_called_with("fast")
    assert mock_button.set_led_state.call_count == 5
