"""Tests for the Niko Home Control Light platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import find_update_callback, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.niko_home_control.PLATFORMS", [Platform.LIGHT]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("light_id", "data", "set_brightness"),
    [
        (0, {ATTR_ENTITY_ID: "light.light"}, 255),
        (
            1,
            {ATTR_ENTITY_ID: "light.dimmable_light", ATTR_BRIGHTNESS: 50},
            50,
        ),
    ],
)
async def test_turning_on(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    light_id: int,
    data: dict[str, Any],
    set_brightness: int,
) -> None:
    """Test turning on the light."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        data,
        blocking=True,
    )
    mock_niko_home_control_connection.lights[light_id].turn_on.assert_called_once_with(
        set_brightness
    )


@pytest.mark.parametrize(
    ("light_id", "entity_id"),
    [
        (0, "light.light"),
        (1, "light.dimmable_light"),
    ],
)
async def test_turning_off(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    light_id: int,
    entity_id: str,
) -> None:
    """Test turning on the light."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_niko_home_control_connection.lights[
        light_id
    ].turn_off.assert_called_once_with()


async def test_updating(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    light: AsyncMock,
    dimmable_light: AsyncMock,
) -> None:
    """Test turning on the light."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.light").state == STATE_ON

    light.state = 0
    await find_update_callback(mock_niko_home_control_connection, 1)(0)
    await hass.async_block_till_done()

    assert hass.states.get("light.light").state == STATE_OFF

    assert hass.states.get("light.dimmable_light").state == STATE_ON
    assert hass.states.get("light.dimmable_light").attributes[ATTR_BRIGHTNESS] == 255

    dimmable_light.state = 204
    await find_update_callback(mock_niko_home_control_connection, 2)(204)
    await hass.async_block_till_done()

    assert hass.states.get("light.dimmable_light").state == STATE_ON
    assert hass.states.get("light.dimmable_light").attributes[ATTR_BRIGHTNESS] == 204

    dimmable_light.state = 0
    await find_update_callback(mock_niko_home_control_connection, 2)(0)
    await hass.async_block_till_done()

    assert hass.states.get("light.dimmable_light").state == STATE_OFF
    assert hass.states.get("light.dimmable_light").attributes[ATTR_BRIGHTNESS] is None
