"""Test the OpenDisplay button event platform."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    TEST_ADDRESS,
    make_binary_inputs,
    make_button_device_config,
    make_v1_service_info,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_no_entities_without_binary_inputs(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """No event entities are created when the device has no binary inputs configured."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert not any(e.domain == "event" for e in entries)


async def test_entities_created_per_active_button(
    hass: HomeAssistant,
    mock_three_button_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """One event entity is created per active button bit in binary_inputs."""
    mock_three_button_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(
        mock_three_button_config_entry.entry_id
    )
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_three_button_config_entry.entry_id
    )
    event_entries = [e for e in entries if e.domain == "event"]
    assert len(event_entries) == 3
    assert {e.unique_id for e in event_entries} == {
        f"{TEST_ADDRESS}-button_0_0",
        f"{TEST_ADDRESS}-button_0_1",
        f"{TEST_ADDRESS}-button_0_2",
    }


async def test_multiple_binary_input_instances(
    hass: HomeAssistant,
    mock_multi_instance_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Entities across multiple BinaryInputs instances get globally sequential button numbers."""
    mock_multi_instance_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(
        mock_multi_instance_config_entry.entry_id
    )
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_multi_instance_config_entry.entry_id
    )
    event_entries = [e for e in entries if e.domain == "event"]
    assert len(event_entries) == 3
    assert {e.unique_id for e in event_entries} == {
        f"{TEST_ADDRESS}-button_0_0",
        f"{TEST_ADDRESS}-button_0_1",
        f"{TEST_ADDRESS}-button_1_0",
    }
    # Button numbers must be globally sequential, not reset per instance
    names = {
        e.unique_id: hass.states.get(e.entity_id).attributes.get("friendly_name", "")
        for e in event_entries
    }
    assert names[f"{TEST_ADDRESS}-button_0_0"].endswith("Button 1")
    assert names[f"{TEST_ADDRESS}-button_0_1"].endswith("Button 2")
    assert names[f"{TEST_ADDRESS}-button_1_0"].endswith("Button 3")


async def test_stale_entities_removed_on_config_change(
    hass: HomeAssistant,
    mock_two_button_config_entry: MockConfigEntry,
    mock_opendisplay_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Entities for buttons no longer in device config are removed on reload."""
    mock_two_button_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_two_button_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        len(
            [
                e
                for e in er.async_entries_for_config_entry(
                    entity_registry, mock_two_button_config_entry.entry_id
                )
                if e.domain == "event"
            ]
        )
        == 2
    )

    # Device reconfigured: now only 1 active button
    mock_opendisplay_device.config = make_button_device_config(
        [make_binary_inputs(input_flags=0x01)]
    )
    assert await hass.config_entries.async_unload(mock_two_button_config_entry.entry_id)
    assert await hass.config_entries.async_setup(mock_two_button_config_entry.entry_id)
    await hass.async_block_till_done()

    event_entries = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_two_button_config_entry.entry_id
        )
        if e.domain == "event"
    ]
    assert len(event_entries) == 1
    assert event_entries[0].unique_id == f"{TEST_ADDRESS}-button_0_0"


async def test_button_down_event_fired(
    hass: HomeAssistant,
    mock_button_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A 'button_down' event fires when the button transitions to the down state."""
    mock_button_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_button_config_entry.entry_id)
    await hass.async_block_till_done()

    # First advertisement — seeds tracker state (no events emitted)
    inject_bluetooth_service_info(hass, make_v1_service_info())
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "event", "opendisplay", f"{TEST_ADDRESS}-button_0_0"
    )
    assert entity_id is not None
    state_before = hass.states.get(entity_id)

    # Second advertisement — byte 0: pressed=True, button_id=0 → raw=0x80
    inject_bluetooth_service_info(hass, make_v1_service_info(b"\x80" + b"\x00" * 10))
    await hass.async_block_till_done()

    state_after = hass.states.get(entity_id)
    assert state_after is not None
    assert state_after.attributes.get("event_type") == "button_down"
    assert state_before != state_after


async def test_button_up_event_fired(
    hass: HomeAssistant,
    mock_button_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A 'button_up' event fires when the button transitions from down to up."""
    mock_button_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_button_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "event", "opendisplay", f"{TEST_ADDRESS}-button_0_0"
    )
    assert entity_id is not None

    # Seed with pressed state (pressed=True, button_id=0 → raw=0x80)
    inject_bluetooth_service_info(hass, make_v1_service_info(b"\x80" + b"\x00" * 10))
    await hass.async_block_till_done()

    # Transition to released (pressed=False, button_id=0 → raw=0x00)
    inject_bluetooth_service_info(hass, make_v1_service_info())
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("event_type") == "button_up"


async def test_no_event_for_wrong_button_id(
    hass: HomeAssistant,
    mock_two_button_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Entity watching button_id=1 does not fire when button_id=0 changes."""
    mock_two_button_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_two_button_config_entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, make_v1_service_info())
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "event", "opendisplay", f"{TEST_ADDRESS}-button_0_1"
    )
    assert entity_id is not None
    state_before = hass.states.get(entity_id)

    # Press button_id=0 only (raw=0x80: pressed=True, button_id=0)
    inject_bluetooth_service_info(hass, make_v1_service_info(b"\x80" + b"\x00" * 10))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) == state_before
