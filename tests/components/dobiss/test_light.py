"""Verify user-facing light behavior."""

from asyncio import Event
from datetime import timedelta
from unittest.mock import AsyncMock

from dobiss_nxt import DobissConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import LIGHTS


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Create the controller and its lights."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()


async def test_state(hass: HomeAssistant) -> None:
    """Expose on/off and brightness according to each output capability."""
    kitchen = hass.states.get("light.kitchen")
    assert kitchen.state == "on"
    assert kitchen.attributes["friendly_name"] == "Kitchen"
    assert kitchen.attributes["brightness"] == 128
    assert kitchen.attributes["supported_color_modes"] == ["brightness"]
    hall = hass.states.get("light.hall")
    assert hall.state == "off"
    assert hall.attributes["friendly_name"] == "Hall"
    assert hall.attributes["supported_color_modes"] == ["onoff"]


@pytest.mark.parametrize(
    ("service", "extra", "on", "brightness", "state", "expected_brightness"),
    [
        ("turn_on", {"brightness": 255}, True, 100, "on", 255),
        ("turn_on", {"brightness": 1}, True, 1, "on", 3),
        ("turn_on", {}, True, None, "on", 128),
        ("turn_off", {}, False, None, "off", None),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    service: str,
    extra: dict[str, int],
    on: bool,
    brightness: int | None,
    state: str,
    expected_brightness: int | None,
) -> None:
    """Publish accepted commands immediately without another REST request."""
    await hass.services.async_call(
        "light",
        service,
        {ATTR_ENTITY_ID: "light.kitchen"} | extra,
        blocking=True,
    )
    mock_client.set_light.assert_awaited_once_with(
        LIGHTS[0], on=on, brightness=brightness
    )
    assert mock_client.light_states.await_count == 1
    updated = hass.states.get("light.kitchen")
    assert updated.state == state
    assert updated.attributes["brightness"] == expected_brightness


async def test_command_error(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """A failed command must be reported to the caller."""
    mock_client.set_light.side_effect = DobissConnectionError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light", "turn_off", {ATTR_ENTITY_ID: "light.kitchen"}, blocking=True
        )
    assert hass.states.get("light.kitchen").state == "on"


async def test_immediate_toggle(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """A second toggle uses the accepted state without waiting for polling."""
    await hass.services.async_call(
        "light", "toggle", {ATTR_ENTITY_ID: "light.hall"}, blocking=True
    )
    assert hass.states.get("light.hall").state == "on"
    await hass.services.async_call(
        "light", "toggle", {ATTR_ENTITY_ID: "light.hall"}, blocking=True
    )
    assert hass.states.get("light.hall").state == "off"
    assert mock_client.set_light.await_args_list[0].kwargs["on"] is True
    assert mock_client.set_light.await_args_list[1].kwargs["on"] is False
    assert mock_client.light_states.await_count == 1


async def test_poll_confirms_command(
    hass: HomeAssistant, mock_client: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Controller feedback remains authoritative after immediate command feedback."""
    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: "light.hall"}, blocking=True
    )
    assert hass.states.get("light.hall").state == "on"
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("light.hall").state == "off"


@pytest.mark.parametrize("states", [{"4_0": None, "2_0": 0}, {"2_0": 0}])
async def test_missing_and_recovery(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    states: dict[str, int | None],
) -> None:
    """Missing outputs become unavailable and recover when status returns."""
    mock_client.light_states.return_value = states
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("light.kitchen").state == STATE_UNAVAILABLE
    mock_client.light_states.return_value = {"4_0": 100, "2_0": 1}
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("light.kitchen").state == "on"


async def test_poll_failure(
    hass: HomeAssistant, mock_client: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Connection loss makes all lights unavailable until the next successful poll."""
    mock_client.light_states.side_effect = DobissConnectionError
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("light.hall").state == STATE_UNAVAILABLE
    mock_client.light_states.side_effect = None
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("light.hall").state == "off"


async def test_commands_preserve_polling_deadline(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Repeated commands do not postpone shared status updates."""
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.light_states.reset_mock()
    freezer.tick(timedelta(seconds=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: "light.hall"}, blocking=True
    )
    assert hass.states.get("light.hall").state == "on"

    freezer.tick(timedelta(seconds=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: "light.hall"}, blocking=True
    )
    assert mock_client.light_states.await_count == 0

    mock_client.light_states.return_value = {"4_0": None, "2_0": 0}
    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_client.light_states.await_count == 1
    assert hass.states.get("light.hall").state == "off"
    assert hass.states.get("light.kitchen").state == STATE_UNAVAILABLE


async def test_poll_queued_behind_command(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    mock_entry: MockConfigEntry,
) -> None:
    """A poll corrects command feedback even when its result equals the old state."""
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.light_states.reset_mock()
    command_started = Event()
    release_command = Event()

    async def delayed_command(*args: object, **kwargs: object) -> None:
        command_started.set()
        await release_command.wait()

    mock_client.set_light.side_effect = delayed_command
    command = hass.async_create_background_task(
        mock_entry.runtime_data.async_set_light(LIGHTS[1], on=True),
        "Dobiss delayed test command",
    )
    await command_started.wait()
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=False)
    assert mock_client.light_states.await_count == 0
    release_command.set()
    await command
    await hass.async_block_till_done()
    assert mock_client.light_states.await_count == 1
    assert hass.states.get("light.hall").state == "off"
