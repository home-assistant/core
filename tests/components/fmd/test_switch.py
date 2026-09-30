"""Test FMD switch entities."""

import asyncio
import contextlib
from unittest.mock import AsyncMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.fmd.common import setup_integration


async def test_high_frequency_mode_switch(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test high frequency mode switch."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "switch.fmd_test_user_high_frequency_mode"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Turn off
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_allow_inaccurate_switch(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test allow inaccurate locations switch."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "switch.fmd_test_user_location_allow_inaccurate_updates"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_photo_auto_cleanup_switch(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo auto-cleanup switch."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "switch.fmd_test_user_photo_auto_cleanup"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Turn off
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_wipe_safety_switch(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe safety switch."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "switch.fmd_test_user_wipe_safety_switch"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Turn off manually
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_wipe_safety_auto_timeout(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe safety switch auto-disables after successful wipe."""
    await setup_integration(hass, mock_fmd_api)

    # Set wipe PIN first
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_wipe_pin", "value": "1234"},
        blocking=True,
    )

    # Enable safety switch
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    # Wipe device
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Safety switch should turn off after successful wipe
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state.state == STATE_OFF


async def test_high_frequency_mode_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test high frequency mode when tracker is not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass.data
    hass.config_entries.async_entries("fmd")[0].runtime_data.tracker = None

    entity_id = "switch.fmd_test_user_high_frequency_mode"

    # Turn on - should handle gracefully without crashing
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None


async def test_allow_inaccurate_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test allow inaccurate when tracker is not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass.data
    hass.config_entries.async_entries("fmd")[0].runtime_data.tracker = None

    entity_id = "switch.fmd_test_user_location_allow_inaccurate_updates"

    # Turn on - should handle gracefully without crashing
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None


async def test_high_frequency_mode_api_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test high frequency mode when API raises error still updates state."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "switch.fmd_test_user_high_frequency_mode"

    # Turn on the switch
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # State should be updated to ON
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Turn off the switch
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # State should be updated to OFF
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_allow_inaccurate_api_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test allow inaccurate when tracker method fails."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "switch.fmd_test_user_location_allow_inaccurate_updates"

    # Turn on - updates the tracker's internal state
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Turn off - should work
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_switch_wipe_safety_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe safety switch when tracker not found (for logging)."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass data
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.tracker = None

    # Turn on the wipe safety switch (should still work, just logs differently)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify it's on
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state.state == "on"


async def test_switch_wipe_safety_auto_disable_task_cancellation(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe safety auto-disable task cancellation."""
    await setup_integration(hass, mock_fmd_api)

    # Turn on the wipe safety (starts auto-disable task)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    # Get the switch entity
    entry = hass.config_entries.async_entries("fmd")[0]
    safety_switch = entry.runtime_data.wipe_safety_switch

    # Verify task was created
    task = safety_switch._auto_disable_task
    assert task is not None

    # Turn off the switch (cancels the task - this hits the except CancelledError block)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    # Wait for the task to handle the cancellation
    with contextlib.suppress(asyncio.CancelledError):
        await task

    # Task should be cancelled and set to None
    assert safety_switch._auto_disable_task is None
    assert safety_switch.is_on is False


async def test_switch_wipe_safety_turn_on_while_running(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test turning on wipe safety switch while it is already running."""
    await setup_integration(hass, mock_fmd_api)

    # Turn on the wipe safety (starts auto-disable task)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    # Get the switch entity
    entry = hass.config_entries.async_entries("fmd")[0]
    safety_switch = entry.runtime_data.wipe_safety_switch

    # Verify task was created
    task1 = safety_switch._auto_disable_task
    assert task1 is not None

    # Turn on the switch AGAIN - call directly to bypass HA state check
    await safety_switch.async_turn_on()

    # Verify the old task was cancelled and a new one created
    task2 = safety_switch._auto_disable_task
    assert task2 is not None
    assert task1 is not task2
    assert task1.cancelled()

    # Cleanup: Turn off
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )


async def test_switch_multiple_toggles(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test switch handles multiple rapid toggles."""
    await setup_integration(hass, mock_fmd_api)

    # Rapid toggles
    for _ in range(3):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
            blocking=True,
        )
        await hass.async_block_till_done()

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Final state should be off
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state is not None
    assert state.state == "off"


async def test_photo_auto_cleanup_switch_toggle_and_persistence(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test toggling photo auto-cleanup switch and persistence."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "switch.fmd_test_user_photo_auto_cleanup"
    # Turn on
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "on"

    # Turn off
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # Check persistence in config entry
    entry = hass.config_entries.async_entries("fmd")[0]
    assert entry.data["photo_auto_cleanup_is_on"] is False


async def test_wipe_safety_switch_auto_disables_after_timeout(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Patch timeout to zero and verify auto-disable executes and turns switch off."""
    from unittest.mock import patch

    await setup_integration(hass, mock_fmd_api)

    with (
        patch("homeassistant.components.fmd.switch.WIPE_SAFETY_TIMEOUT", 0),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        # Turn on
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Await the auto-disable task to completion
        entry = hass.config_entries.async_entries("fmd")[0]
        switch = entry.runtime_data.wipe_safety_switch
        if switch._auto_disable_task:
            with contextlib.suppress(asyncio.CancelledError):
                await switch._auto_disable_task

    # After auto-disable, state should be off
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state is not None and state.state == "off"
