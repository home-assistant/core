"""Tests for the Nanoleaf light platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    LightEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import ESSENTIALS_CURRENT_EFFECT, ESSENTIALS_EFFECTS

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_turning_on_or_off_writes_state(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test turning on or off the light writes the state."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.nanoleaf").attributes[ATTR_EFFECT_LIST] == [
        "Rainbow",
        "Sunset",
        "Nemo",
    ]

    mock_nanoleaf.effects_list = ["Rainbow", "Sunset", "Nemo", "Something Else"]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: "light.nanoleaf",
        },
        blocking=True,
    )
    assert hass.states.get("light.nanoleaf").attributes[ATTR_EFFECT_LIST] == [
        "Rainbow",
        "Sunset",
        "Nemo",
        "Something Else",
    ]


async def test_essentials_device_has_effects(
    hass: HomeAssistant,
    mock_nanoleaf_essentials: AsyncMock,
    mock_config_entry_essentials: MockConfigEntry,
) -> None:
    """Test Essentials device has effects support via HTTP API."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry_essentials)

    state = hass.states.get("light.rope_lights")
    assert state is not None
    # Essentials devices should have effect list (fetched via HTTP)
    assert ATTR_EFFECT_LIST in state.attributes
    assert state.attributes[ATTR_EFFECT_LIST] == ESSENTIALS_EFFECTS
    # Essentials devices should have EFFECT feature
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & LightEntityFeature.EFFECT
    # And should have TRANSITION feature
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & LightEntityFeature.TRANSITION
    # Current effect should be set
    assert state.attributes.get(ATTR_EFFECT) == ESSENTIALS_CURRENT_EFFECT


async def test_essentials_device_turn_on(
    hass: HomeAssistant,
    mock_nanoleaf_essentials: AsyncMock,
    mock_config_entry_essentials: MockConfigEntry,
) -> None:
    """Test turning on Essentials device."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry_essentials)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.rope_lights",
        },
        blocking=True,
    )
    mock_nanoleaf_essentials.turn_on.assert_called_once()


async def test_essentials_device_turn_on_with_color(
    hass: HomeAssistant,
    mock_nanoleaf_essentials: AsyncMock,
    mock_config_entry_essentials: MockConfigEntry,
) -> None:
    """Test turning on Essentials device with color."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry_essentials)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.rope_lights",
            ATTR_HS_COLOR: [120, 50],
        },
        blocking=True,
    )
    mock_nanoleaf_essentials.set_hue.assert_called_once_with(120)
    mock_nanoleaf_essentials.set_saturation.assert_called_once_with(50)


async def test_essentials_device_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_nanoleaf_essentials: AsyncMock,
    mock_config_entry_essentials: MockConfigEntry,
) -> None:
    """Test turning on Essentials device with brightness."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry_essentials)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.rope_lights",
            ATTR_BRIGHTNESS: 127,  # ~50% in HA scale (0-255)
        },
        blocking=True,
    )
    mock_nanoleaf_essentials.turn_on.assert_called_once()
    # 127 / 2.55 ≈ 49
    mock_nanoleaf_essentials.set_brightness.assert_called_once_with(49)


async def test_essentials_device_set_effect(
    hass: HomeAssistant,
    mock_nanoleaf_essentials: AsyncMock,
    mock_config_entry_essentials: MockConfigEntry,
    mock_essentials_aiohttp_session,
) -> None:
    """Test setting effect on Essentials device via HTTP API."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry_essentials)

    # Verify the effect list is available
    state = hass.states.get("light.rope_lights")
    assert state is not None
    assert ATTR_EFFECT_LIST in state.attributes

    # Set an effect
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.rope_lights",
            ATTR_EFFECT: "Neon Flex",
        },
        blocking=True,
    )
    # The effect should be set via HTTP, not via the library
    # The library's set_effect should NOT be called for Essentials
    mock_nanoleaf_essentials.set_effect.assert_not_called()
