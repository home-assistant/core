"""Test the wmspro scene support."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.wmspro.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_config_entry

from tests.common import MockConfigEntry


async def test_scene_room_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_test: AsyncMock,
    mock_dest_refresh: AsyncMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a scene room device is created correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_test.mock_calls) == 1

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "42581")})
    assert device_entry is not None
    assert device_entry == snapshot


async def test_scene_activate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_test: AsyncMock,
    mock_dest_refresh: AsyncMock,
    mock_scene_call: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a scene entity is created and activated correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_test.mock_calls) == 1

    entity = hass.states.get("scene.raum_0_gute_nacht")
    assert entity is not None
    assert entity == snapshot

    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=True,
    )

    assert len(mock_scene_call.mock_calls) == 1
