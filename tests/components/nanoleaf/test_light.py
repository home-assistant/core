"""Tests for the Nanoleaf light platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.light import ATTR_EFFECT_LIST, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

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
