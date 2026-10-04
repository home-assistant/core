"""Test KNX activity attribution."""

import asyncio
from datetime import timedelta

import pytest
from xknx.dpt import DPTBinary
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.address import GroupAddress, IndividualAddress
from xknx.telegram.apci import GroupValueResponse, GroupValueWrite

from homeassistant.components.knx.const import EVENT_KNX_STATE_CHANGED, KNX_MODULE_KEY
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import MockUser, async_capture_events
from tests.components.recorder.common import async_wait_recording_done
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    ("address", "telegram_type"),
    [
        pytest.param("1/1/1", GroupValueWrite, id="command"),
        pytest.param("1/1/2", GroupValueWrite, id="status-write"),
        pytest.param("1/1/2", GroupValueResponse, id="status-response"),
    ],
)
@pytest.mark.parametrize("platform", ["light", "switch"])
async def test_telegram_context(
    hass: HomeAssistant,
    knx: KNXTestKit,
    platform: str,
    address: str,
    telegram_type: type[GroupValueWrite | GroupValueResponse],
) -> None:
    """Attribute a switch value to the actual sender, including status senders."""
    await knx.setup_integration(
        {platform: {"name": "test", "address": "1/1/1", "state_address": "1/1/2"}},
        state_updater=False,
    )
    await knx.receive_response("1/1/2", False)
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    knx.xknx.telegrams.put_nowait(
        Telegram(
            destination_address=GroupAddress(address),
            source_address=IndividualAddress("1.1.23"),
            direction=TelegramDirection.INCOMING,
            payload=telegram_type(DPTBinary(True)),
        )
    )
    await knx.xknx.telegrams.join()
    await hass.async_block_till_done()

    state = hass.states.get(f"{platform}.test")
    assert state.state == STATE_ON
    assert len(events) == 1
    assert events[0].data == {
        "source": "1.1.23",
        "source_name": "",
        "destination": address,
        "destination_name": "",
        "telegramtype": telegram_type.__name__,
    }
    assert state.context is events[0].context
    assert state.context.user_id is None

    # A matching status telegram must not replace the command's attribution.
    await knx.receive_write("1/1/2", True, source="1.1.40")
    assert len(events) == 1
    assert hass.states.get(f"{platform}.test").context is state.context

    await knx.receive_write("1/1/1", False, source="1.1.24")
    assert len(events) == 2
    assert hass.states.get(f"{platform}.test").context is events[1].context
    assert events[1].context.id != events[0].context.id
    assert events[1].data["source"] == "1.1.24"


@pytest.mark.parametrize("platform", ["light", "switch"])
async def test_service_context(
    hass: HomeAssistant, knx: KNXTestKit, hass_admin_user: MockUser, platform: str
) -> None:
    """Preserve HA causes and replace them when a physical switch takes over."""
    await knx.setup_integration({platform: {"name": "test", "address": "1/1/1"}})
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    service_context = Context(user_id=hass_admin_user.id, parent_id=Context().id)

    await hass.services.async_call(
        platform,
        "turn_on",
        {"entity_id": f"{platform}.test"},
        blocking=True,
        context=service_context,
    )
    await knx.assert_write("1/1/1", True)
    assert hass.states.get(f"{platform}.test").context is service_context
    assert not events

    # This happens inside HA's recent-context window.
    await knx.receive_write("1/1/1", False, source="1.1.23")
    assert hass.states.get(f"{platform}.test").context is events[0].context
    assert events[0].context.user_id is None
    assert events[0].context.parent_id is None

    next_context = Context(parent_id=Context().id)
    await hass.services.async_call(
        platform,
        "turn_on",
        {"entity_id": f"{platform}.test"},
        blocking=True,
        context=next_context,
    )
    await knx.assert_write("1/1/1", True)
    assert hass.states.get(f"{platform}.test").context is next_context
    assert len(events) == 1


async def test_light_brightness_does_not_reuse_sender(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Attribute switching on dimmable lights without reusing stale switch telegrams."""
    await knx.setup_integration(
        {
            "light": {
                "name": "test",
                "address": "1/1/1",
                "brightness_address": "1/1/3",
            }
        }
    )
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    await knx.receive_write("1/1/1", True, source="1.1.23")
    context = hass.states.get("light.test").context
    assert context is events[0].context

    await knx.receive_write("1/1/3", (128,), source="1.1.40")
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 128
    assert state.context.id != context.id
    assert len(events) == 1

    await knx.receive_read("1/1/1")
    await knx.receive_write("1/1/9", False, source="1.1.24")
    assert len(events) == 1


async def test_shared_telegram_context(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """One telegram affecting multiple lights has one originating event."""
    await knx.setup_integration(
        {
            "light": [
                {"name": "one", "unique_id": "one", "address": "1/1/1"},
                {"name": "two", "unique_id": "two", "address": "1/1/1"},
            ]
        }
    )
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    await knx.receive_write("1/1/1", True, source="1.1.23")

    assert len(events) == 1
    assert hass.states.get("light.one").context is events[0].context
    assert hass.states.get("light.two").context is events[0].context


async def test_ui_light_telegram_context(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Apply the same attribution to lights configured in the UI."""
    await knx.setup_integration()
    entry = await create_ui_entity(
        platform=Platform.LIGHT,
        knx_data={"ga_switch": {"write": "1/1/1"}},
    )
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    await knx.receive_write("1/1/1", True, source="1.1.23")

    assert len(events) == 1
    assert hass.states.get(entry.entity_id).context is events[0].context


@pytest.mark.usefixtures("recorder_mock")
async def test_light_live_activity(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Resolve the sender in a live activity subscription filtered to the light."""
    assert await async_setup_component(hass, "logbook", {})
    await knx.setup_integration({"light": {"name": "test", "address": "1/1/1"}})
    await async_wait_recording_done(hass)
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/event_stream",
            "start_time": (dt_util.utcnow() - timedelta(seconds=1)).isoformat(),
            "entity_ids": ["light.test"],
        }
    )
    result = await asyncio.wait_for(client.receive_json(), 2)
    assert result["success"]
    # Consume the recent-history and backfill batches before the live change.
    for _ in range(2):
        history = await asyncio.wait_for(client.receive_json(), 2)
        assert history["type"] == "event"

    await knx.receive_write("1/1/1", True, source="1.1.23")
    message = await asyncio.wait_for(client.receive_json(), 2)
    assert message["type"] == "event"
    entries = message["event"]["events"]
    assert len(entries) == 1
    assert entries[0]["entity_id"] == "light.test"
    assert entries[0]["context_name"] == "1.1.23"
    assert entries[0]["context_event_type"] == EVENT_KNX_STATE_CHANGED


@pytest.mark.usefixtures("recorder_mock", "load_knxproj")
@pytest.mark.parametrize(
    ("source", "expected_name"),
    [
        pytest.param("1.1.23", "1.1.23", id="individual-address"),
        pytest.param(
            "1.0.0",
            "Weinzierl Engineering GmbH KNX IP Router 752 secure (1.0.0)",
            id="project-name",
        ),
    ],
)
async def test_light_recorded_activity(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    source: str,
    expected_name: str,
) -> None:
    """Resolve the sender from recorded events in entity-filtered activity."""
    start = dt_util.utcnow() - timedelta(seconds=1)
    assert await async_setup_component(hass, "logbook", {})
    await knx.setup_integration({"light": {"name": "test", "address": "1/1/1"}})
    await knx.receive_write("1/1/1", True, source=source)
    await async_wait_recording_done(hass)

    # Historical names must survive removal of the ETS project.
    hass.data[KNX_MODULE_KEY].project.devices.clear()
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": start.isoformat(),
            "entity_ids": ["light.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    entries = [entry for entry in response["result"] if entry.get("state") == STATE_ON]
    assert len(entries) == 1
    assert entries[0]["entity_id"] == "light.test"
    assert entries[0]["context_name"] == expected_name
    assert entries[0]["context_domain"] == "knx"
    assert entries[0]["context_event_type"] == EVENT_KNX_STATE_CHANGED
    assert "context_user_id" not in entries[0]
