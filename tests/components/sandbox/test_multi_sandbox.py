"""Test multiple sandboxes with area/device/entity targeting."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.components.sandbox.const import DATA_SANDBOX
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    mock_platform,
    MockEntity,
    MockPlatform,
)
from tests.typing import WebSocketGenerator


@pytest.fixture
def ignore_translations_for_mock_domains() -> list[str]:
    """Don't check translations for our mock domains."""
    return ["test_native"]


class MockNativeLight(LightEntity):
    """A native light entity on the host."""

    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_should_poll = False

    def __init__(self, unique_id: str, name: str, device_info: DeviceInfo) -> None:
        """Initialize."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_info = device_info
        self._attr_is_on = False
        self._attr_brightness = 0
        self.turn_on_calls: list[dict] = []
        self.turn_off_calls: list[dict] = []

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on."""
        self._attr_is_on = True
        self._attr_brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self.turn_on_calls.append(kwargs)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off."""
        self._attr_is_on = False
        self.turn_off_calls.append(kwargs)
        self.async_write_ha_state()


@pytest.fixture
async def multi_sandbox_setup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> dict:
    """Set up 2 sandboxes + 1 native light, all in the same area."""
    assert await async_setup_component(hass, "sandbox", {})
    assert await async_setup_component(hass, "light", {})

    # Create area
    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Living Room")

    # --- Sandbox A: "Hue light" ---
    sandbox_a_id = "sandbox_a_001"
    entry_a = MockConfigEntry(
        domain="sandbox",
        entry_id=sandbox_a_id,
        data={
            "entries": [
                {
                    "entry_id": "hue_entry_a",
                    "domain": "hue",
                    "title": "Hue Bridge",
                    "data": {},
                }
            ]
        },
    )
    entry_a.add_to_hass(hass)

    # --- Sandbox B: "IKEA light" ---
    sandbox_b_id = "sandbox_b_002"
    entry_b = MockConfigEntry(
        domain="sandbox",
        entry_id=sandbox_b_id,
        data={
            "entries": [
                {
                    "entry_id": "ikea_entry_b",
                    "domain": "ikea",
                    "title": "IKEA Gateway",
                    "data": {},
                }
            ]
        },
    )
    entry_b.add_to_hass(hass)

    with patch(
        "homeassistant.components.sandbox._spawn_sandbox",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry_a.entry_id)
        await hass.config_entries.async_setup(entry_b.entry_id)

    await hass.async_block_till_done()

    sandbox_data = hass.data[DATA_SANDBOX]

    # Connect sandbox A ws client
    instance_a = sandbox_data.sandboxes[sandbox_a_id]
    ws_a = await hass_ws_client(hass, access_token=instance_a.access_token)

    # Connect sandbox B ws client
    instance_b = sandbox_data.sandboxes[sandbox_b_id]
    ws_b = await hass_ws_client(hass, access_token=instance_b.access_token)

    # Subscribe both to entity commands
    await ws_a.send_json({"id": 1, "type": "sandbox/subscribe_entity_commands"})
    resp = await ws_a.receive_json()
    assert resp["success"]

    await ws_b.send_json({"id": 1, "type": "sandbox/subscribe_entity_commands"})
    resp = await ws_b.receive_json()
    assert resp["success"]

    # Register device + light for sandbox A
    device_reg = dr.async_get(hass)

    await ws_a.send_json(
        {
            "id": 2,
            "type": "sandbox/register_device",
            "sandbox_entry_id": "hue_entry_a",
            "identifiers": [{"domain": "hue", "id": "hue_bulb_1"}],
            "name": "Hue Bulb",
            "manufacturer": "Philips",
        }
    )
    resp = await ws_a.receive_json()
    assert resp["success"]
    device_a_id = resp["result"]["device_id"]

    # Assign device A to area
    device_reg.async_update_device(device_a_id, area_id=area.id)

    await ws_a.send_json(
        {
            "id": 3,
            "type": "sandbox/register_entity",
            "sandbox_entry_id": "hue_entry_a",
            "domain": "light",
            "platform": "hue",
            "unique_id": "hue_bulb_1_light",
            "device_id": device_a_id,
            "original_name": "Hue Bulb",
            "supported_features": 0,
            "capabilities": {"supported_color_modes": ["brightness"]},
            "suggested_object_id": "hue_bulb",
        }
    )
    resp = await ws_a.receive_json()
    assert resp["success"]
    entity_a_id = resp["result"]["entity_id"]

    # Push initial state for A
    await ws_a.send_json(
        {
            "id": 4,
            "type": "sandbox/update_state",
            "entity_id": entity_a_id,
            "state": "off",
            "attributes": {"brightness": None, "color_mode": None},
        }
    )
    resp = await ws_a.receive_json()
    assert resp["success"]

    # Register device + light for sandbox B
    await ws_b.send_json(
        {
            "id": 2,
            "type": "sandbox/register_device",
            "sandbox_entry_id": "ikea_entry_b",
            "identifiers": [{"domain": "ikea", "id": "ikea_bulb_1"}],
            "name": "IKEA Bulb",
            "manufacturer": "IKEA",
        }
    )
    resp = await ws_b.receive_json()
    assert resp["success"]
    device_b_id = resp["result"]["device_id"]

    # Assign device B to same area
    device_reg.async_update_device(device_b_id, area_id=area.id)

    await ws_b.send_json(
        {
            "id": 3,
            "type": "sandbox/register_entity",
            "sandbox_entry_id": "ikea_entry_b",
            "domain": "light",
            "platform": "ikea",
            "unique_id": "ikea_bulb_1_light",
            "device_id": device_b_id,
            "original_name": "IKEA Bulb",
            "supported_features": 0,
            "capabilities": {"supported_color_modes": ["brightness"]},
            "suggested_object_id": "ikea_bulb",
        }
    )
    resp = await ws_b.receive_json()
    assert resp["success"]
    entity_b_id = resp["result"]["entity_id"]

    # Push initial state for B
    await ws_b.send_json(
        {
            "id": 4,
            "type": "sandbox/update_state",
            "entity_id": entity_b_id,
            "state": "off",
            "attributes": {"brightness": None, "color_mode": None},
        }
    )
    resp = await ws_b.receive_json()
    assert resp["success"]

    # --- Native light on host ---
    native_entry = MockConfigEntry(domain="test_native", entry_id="native_entry_1")
    native_entry.add_to_hass(hass)

    native_device = device_reg.async_get_or_create(
        config_entry_id=native_entry.entry_id,
        identifiers={("test_native", "ceiling_1")},
        name="Ceiling Light",
        manufacturer="Generic",
    )
    device_reg.async_update_device(native_device.id, area_id=area.id)

    native_light = MockNativeLight(
        "native_ceiling",
        "Ceiling Light",
        DeviceInfo(identifiers={("test_native", "ceiling_1")}),
    )

    from homeassistant.helpers.entity_platform import EntityPlatform
    import logging
    from datetime import timedelta

    platform = EntityPlatform(
        hass=hass,
        logger=logging.getLogger("test"),
        domain="light",
        platform_name="test_native",
        platform=None,
        scan_interval=timedelta(seconds=30),
        entity_namespace=None,
    )
    platform.config_entry = native_entry
    await platform.async_add_entities([native_light])

    native_entity_id = native_light.entity_id

    await hass.async_block_till_done()

    return {
        "hass": hass,
        "area": area,
        "ws_a": ws_a,
        "ws_b": ws_b,
        "entity_a_id": entity_a_id,
        "entity_b_id": entity_b_id,
        "native_entity_id": native_entity_id,
        "native_light": native_light,
        "device_a_id": device_a_id,
        "device_b_id": device_b_id,
        "native_device_id": native_device.id,
    }


async def _respond_to_command(ws, msg_id: int) -> dict:
    """Read one command from the subscription and respond with success."""
    cmd_msg = await asyncio.wait_for(ws.receive_json(), timeout=5)
    assert cmd_msg["type"] == "event"
    event = cmd_msg["event"]

    await ws.send_json(
        {
            "id": msg_id,
            "type": "sandbox/entity_command_result",
            "call_id": event["call_id"],
            "success": True,
        }
    )
    resp = await ws.receive_json()
    assert resp["success"]
    return event


async def test_turn_on_by_entity_id(
    hass: HomeAssistant, multi_sandbox_setup: dict
) -> None:
    """Test turning on each light individually by entity_id."""
    setup = multi_sandbox_setup
    ws_a = setup["ws_a"]
    ws_b = setup["ws_b"]
    native_light = setup["native_light"]

    # Turn on sandbox A light
    task = asyncio.create_task(
        hass.services.async_call(
            "light",
            "turn_on",
            {"brightness": 100},
            target={"entity_id": setup["entity_a_id"]},
            blocking=True,
        )
    )
    event = await _respond_to_command(ws_a, msg_id=10)
    await task

    assert event["method"] == "async_turn_on"
    assert event["entity_id"] == setup["entity_a_id"]
    assert event["kwargs"]["brightness"] == 100

    # Turn on sandbox B light
    task = asyncio.create_task(
        hass.services.async_call(
            "light",
            "turn_on",
            {"brightness": 200},
            target={"entity_id": setup["entity_b_id"]},
            blocking=True,
        )
    )
    event = await _respond_to_command(ws_b, msg_id=10)
    await task

    assert event["method"] == "async_turn_on"
    assert event["entity_id"] == setup["entity_b_id"]
    assert event["kwargs"]["brightness"] == 200

    # Turn on native light
    await hass.services.async_call(
        "light",
        "turn_on",
        {"brightness": 150},
        target={"entity_id": setup["native_entity_id"]},
        blocking=True,
    )
    assert native_light.is_on
    assert native_light.brightness == 150


async def test_turn_off_by_device_id(
    hass: HomeAssistant, multi_sandbox_setup: dict
) -> None:
    """Test turning off by device_id targets the correct sandbox."""
    setup = multi_sandbox_setup
    ws_a = setup["ws_a"]
    ws_b = setup["ws_b"]
    native_light = setup["native_light"]

    # Turn on all lights first (set initial state)
    for ws, eid, msg_id in [
        (ws_a, setup["entity_a_id"], 5),
        (ws_b, setup["entity_b_id"], 5),
    ]:
        await ws.send_json(
            {
                "id": msg_id,
                "type": "sandbox/update_state",
                "entity_id": eid,
                "state": "on",
                "attributes": {"brightness": 255, "color_mode": "brightness"},
            }
        )
        resp = await ws.receive_json()
        assert resp["success"]

    await hass.services.async_call(
        "light",
        "turn_on",
        target={"entity_id": setup["native_entity_id"]},
        blocking=True,
    )

    # Turn off device A → should only affect sandbox A's light
    task = asyncio.create_task(
        hass.services.async_call(
            "light",
            "turn_off",
            target={"device_id": setup["device_a_id"]},
            blocking=True,
        )
    )
    event = await _respond_to_command(ws_a, msg_id=11)
    await task

    assert event["method"] == "async_turn_off"
    assert event["entity_id"] == setup["entity_a_id"]

    # Native light should be unaffected
    assert native_light.is_on

    # Turn off native device
    await hass.services.async_call(
        "light",
        "turn_off",
        target={"device_id": setup["native_device_id"]},
        blocking=True,
    )
    assert not native_light.is_on


async def test_turn_on_by_area(
    hass: HomeAssistant, multi_sandbox_setup: dict
) -> None:
    """Test turning on by area targets all 3 lights."""
    setup = multi_sandbox_setup
    ws_a = setup["ws_a"]
    ws_b = setup["ws_b"]
    native_light = setup["native_light"]
    area = setup["area"]

    # Turn on all lights in the area
    task = asyncio.create_task(
        hass.services.async_call(
            "light",
            "turn_on",
            {"brightness": 180},
            target={"area_id": area.id},
            blocking=True,
        )
    )

    # Both sandbox lights should get commands (order may vary)
    events = []
    for ws, msg_id in [(ws_a, 20), (ws_b, 20)]:
        event = await _respond_to_command(ws, msg_id=msg_id)
        events.append(event)

    await task

    # Verify both sandbox lights received turn_on
    sandbox_entity_ids = {e["entity_id"] for e in events}
    assert setup["entity_a_id"] in sandbox_entity_ids
    assert setup["entity_b_id"] in sandbox_entity_ids

    for event in events:
        assert event["method"] == "async_turn_on"
        assert event["kwargs"]["brightness"] == 180

    # Native light should also be on
    assert native_light.is_on
    assert native_light.brightness == 180


async def test_turn_off_by_area(
    hass: HomeAssistant, multi_sandbox_setup: dict
) -> None:
    """Test turning off by area targets all 3 lights."""
    setup = multi_sandbox_setup
    ws_a = setup["ws_a"]
    ws_b = setup["ws_b"]
    native_light = setup["native_light"]
    area = setup["area"]

    # Set all lights to on first
    for ws, eid, msg_id in [
        (ws_a, setup["entity_a_id"], 5),
        (ws_b, setup["entity_b_id"], 5),
    ]:
        await ws.send_json(
            {
                "id": msg_id,
                "type": "sandbox/update_state",
                "entity_id": eid,
                "state": "on",
                "attributes": {"brightness": 255, "color_mode": "brightness"},
            }
        )
        resp = await ws.receive_json()
        assert resp["success"]

    await hass.services.async_call(
        "light",
        "turn_on",
        target={"entity_id": setup["native_entity_id"]},
        blocking=True,
    )
    assert native_light.is_on

    # Turn off everything in the area
    task = asyncio.create_task(
        hass.services.async_call(
            "light",
            "turn_off",
            target={"area_id": area.id},
            blocking=True,
        )
    )

    # Both sandbox lights should get turn_off commands
    events = []
    for ws, msg_id in [(ws_a, 21), (ws_b, 21)]:
        event = await _respond_to_command(ws, msg_id=msg_id)
        events.append(event)

    await task

    sandbox_entity_ids = {e["entity_id"] for e in events}
    assert setup["entity_a_id"] in sandbox_entity_ids
    assert setup["entity_b_id"] in sandbox_entity_ids

    for event in events:
        assert event["method"] == "async_turn_off"

    # Native light should also be off
    assert not native_light.is_on
