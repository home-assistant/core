"""Tests for the Knocki event platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

from knocki import Event, EventType, Trigger, TriggerDetails
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.knocki.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, load_json_array_fixture, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2022-01-01T12:00:00Z")
async def test_subscription(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subscription."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("event.knc1_w_00000214_aaaa").state == STATE_UNKNOWN

    event_function: Callable[[Event], None] = (
        mock_knocki_client.register_listener.call_args[0][1]
    )

    async def _call_event_function(
        device_id: str = "KNC1-W-00000214", trigger_id: int = 31
    ) -> None:
        event_function(
            Event(
                EventType.TRIGGERED,
                Trigger(
                    device_id=device_id, details=TriggerDetails(trigger_id, "aaaa")
                ),
            )
        )
        await hass.async_block_till_done()

    await _call_event_function(device_id="KNC1-W-00000215")
    assert hass.states.get("event.knc1_w_00000214_aaaa").state == STATE_UNKNOWN

    await _call_event_function(trigger_id=32)
    assert hass.states.get("event.knc1_w_00000214_aaaa").state == STATE_UNKNOWN

    await _call_event_function()
    assert (
        hass.states.get("event.knc1_w_00000214_aaaa").state
        == "2022-01-01T12:00:00.000+00:00"
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_knocki_client.register_listener.return_value.called


async def test_adding_runtime_entities(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can create devices on runtime."""
    mock_knocki_client.get_triggers.return_value = []

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.get("event.knc1_w_00000214_aaaa")

    add_trigger_function: Callable[[Event], None] = (
        mock_knocki_client.register_listener.call_args_list[0][0][1]
    )
    trigger = Trigger.from_dict(load_json_array_fixture("triggers.json", DOMAIN)[0])

    add_trigger_function(Event(EventType.CREATED, trigger))

    assert hass.states.get("event.knc1_w_00000214_aaaa") is not None


async def test_removing_runtime_entities(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can create devices on runtime."""
    mock_knocki_client.get_triggers.return_value = [
        Trigger.from_dict(trigger)
        for trigger in load_json_array_fixture("more_triggers.json", DOMAIN)
    ]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("event.knc1_w_00000214_aaaa") is not None
    assert hass.states.get("event.knc1_w_00000214_bbbb") is not None

    remove_trigger_function: Callable[[Event], Awaitable[None]] = (
        mock_knocki_client.register_listener.call_args_list[1][0][1]
    )
    trigger = Trigger.from_dict(load_json_array_fixture("triggers.json", DOMAIN)[0])

    mock_knocki_client.get_triggers.return_value = [trigger]

    await remove_trigger_function(Event(EventType.DELETED, trigger))

    assert hass.states.get("event.knc1_w_00000214_aaaa") is not None
    assert hass.states.get("event.knc1_w_00000214_bbbb") is None
