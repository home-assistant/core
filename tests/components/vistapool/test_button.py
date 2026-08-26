"""Tests for the Vistapool button platform."""

from collections.abc import Generator
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

from aioaquarite import AquariteError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_capture_events, snapshot_platform

_BUTTON = "button.my_pool_led_next_color"
_LIGHT_ENTITY = "light.my_pool_light"
_LED_DATA = {"main": {"hasLED": 1, "version": 1}, "light": {"status": 0}}


@pytest.fixture(autouse=True)
def _only_button_platform() -> Generator[None]:
    """Restrict integration setup to the button platform for these tests."""
    with patch("homeassistant.components.vistapool.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.fixture(autouse=True)
def _skip_pulse_delay() -> Generator[None]:
    """Skip the LED pulse delay so tests don't actually sleep."""
    with patch("homeassistant.components.vistapool.button._LED_PULSE_DELAY_SECONDS", 0):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the LED-pulse button when hasLED is set."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LED_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_button_not_created_without_led(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test the LED-pulse button is not created when hasLED is 0."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(_BUTTON) is None


async def test_button_press_when_light_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test pressing the button when the light is off just turns it on."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LED_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _BUTTON},
        blocking=True,
    )

    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", "light.status", 1
    )


async def test_button_press_when_light_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test pressing the button when the light is on power-cycles it."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasLED": 1, "version": 1},
        "light": {"status": 1},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _BUTTON},
        blocking=True,
    )

    assert mock_vistapool_client.set_value.await_count == 2
    assert mock_vistapool_client.set_value.await_args_list[0].args == (
        "ABCDEF1234567890",
        "light.status",
        0,
    )
    assert mock_vistapool_client.set_value.await_args_list[1].args == (
        "ABCDEF1234567890",
        "light.status",
        1,
    )


async def test_button_press_rapid_repeat_after_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a second press lands the off/on pulse instead of repeating turn-on.

    Without the optimistic update, the second press would read the stale
    off-state (the Firestore push hasn't round-tripped yet) and send another
    bare light.status=1 — a no-op on the wire that doesn't advance the color.
    """
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LED_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _BUTTON},
        blocking=True,
    )
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _BUTTON},
        blocking=True,
    )

    assert mock_vistapool_client.set_value.await_count == 3
    assert mock_vistapool_client.set_value.await_args_list[0].args == (
        "ABCDEF1234567890",
        "light.status",
        1,
    )
    assert mock_vistapool_client.set_value.await_args_list[1].args == (
        "ABCDEF1234567890",
        "light.status",
        0,
    )
    assert mock_vistapool_client.set_value.await_args_list[2].args == (
        "ABCDEF1234567890",
        "light.status",
        1,
    )


async def test_button_press_does_not_flicker_light_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the pulse never announces off, even for pushes inside the delay."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasLED": 1, "version": 1},
        "light": {"status": 1},
    }
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.vistapool.PLATFORMS",
        [Platform.BUTTON, Platform.LIGHT],
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

        async def _push_during_pulse(_pool_id: str, _path: str, value: int) -> None:
            """Land a stale echo and the off echo inside the pulse delay."""
            if value == 0:
                on_data({"light": {"status": 1}})
                on_data({"light": {"status": 0}})

        mock_vistapool_client.set_value.side_effect = _push_during_pulse

        events = async_capture_events(hass, EVENT_STATE_CHANGED)
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: _BUTTON},
            blocking=True,
        )
        await hass.async_block_till_done()

    light_states = [
        event.data["new_state"].state
        for event in events
        if event.data["entity_id"] == _LIGHT_ENTITY
    ]
    assert STATE_OFF not in light_states
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON


async def test_button_press_pulse_survives_stale_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a stale pre-pulse push cannot let the pulse's off echo through."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasLED": 1, "version": 1},
        "light": {"status": 1},
    }
    mock_config_entry.add_to_hass(hass)

    # Load the light platform too: the pulse's observable effect is on it.
    with patch(
        "homeassistant.components.vistapool.PLATFORMS",
        [Platform.BUTTON, Platform.LIGHT],
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: _BUTTON},
            blocking=True,
        )

        # Stale pre-pulse push still carrying on: must not confirm the final on.
        on_data({"light": {"status": 1}})
        await hass.async_block_till_done()
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON

        # The pulse's off echo must not flicker the light state off.
        on_data({"light": {"status": 0}})
        await hass.async_block_till_done()
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON

        # The final on echo confirms; a later real push then sticks.
        on_data({"light": {"status": 1}})
        await hass.async_block_till_done()
        on_data({"light": {"status": 0}})
        await hass.async_block_till_done()
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF


async def test_button_press_failed_pulse_discards_unsent_write(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a failed final on send does not keep suppressing the real off push."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasLED": 1, "version": 1},
        "light": {"status": 1},
    }
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.vistapool.PLATFORMS",
        [Platform.BUTTON, Platform.LIGHT],
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

        async def _fail_final_on(_pool_id: str, _path: str, value: int) -> None:
            """Acknowledge the off write, fail the final on write."""
            if value:
                raise AquariteError("boom")

        mock_vistapool_client.set_value.side_effect = _fail_final_on

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: _BUTTON},
                blocking=True,
            )

        # The off landed on the cloud; its echo must reach the entity instead
        # of being suppressed by the discarded, never-sent on value.
        on_data({"light": {"status": 0}})
        await hass.async_block_till_done()
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF


async def test_button_press_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the button re-raises HomeAssistantError when the library fails."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LED_DATA)
    mock_vistapool_client.set_value.side_effect = AquariteError("boom")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: _BUTTON},
            blocking=True,
        )
    assert excinfo.value.translation_key == "set_failed"
