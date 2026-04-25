"""Tests for vacuum websocket API."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from homeassistant.components.vacuum import (
    DOMAIN,
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.components.websocket_api import ERR_NOT_FOUND, ERR_NOT_SUPPORTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    MockVacuumWithCleanArea,
    help_async_setup_entry_init,
    help_async_unload_entry,
)

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockModule,
    mock_integration,
    setup_test_component_platform,
)
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("config_flow_fixture")
async def test_get_segments(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test vacuum/get_segments websocket command."""
    segments = [
        Segment(id="seg_1", name="Kitchen"),
        Segment(id="seg_2", name="Living Room"),
        Segment(id="seg_3", name="Bedroom", group="Upstairs"),
    ]
    entity = MockVacuumWithCleanArea(
        name="Testing",
        entity_id="vacuum.testing",
        segments=segments,
    )
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
    )
    setup_test_component_platform(hass, DOMAIN, [entity], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": entity.entity_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"segments": [asdict(seg) for seg in segments]}


async def test_get_segments_entity_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test vacuum/get_segments with unknown entity."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": "vacuum.unknown"}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


@pytest.mark.usefixtures("config_flow_fixture")
async def test_get_segments_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test vacuum/get_segments with entity not supporting CLEAN_AREA."""

    class MockVacuumNoCleanArea(MockEntity, StateVacuumEntity):
        _attr_supported_features = VacuumEntityFeature.STATE | VacuumEntityFeature.START
        _attr_activity = VacuumActivity.DOCKED

    entity = MockVacuumNoCleanArea(name="Testing", entity_id="vacuum.testing")
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
    )
    setup_test_component_platform(hass, DOMAIN, [entity], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": entity.entity_id}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_SUPPORTED
