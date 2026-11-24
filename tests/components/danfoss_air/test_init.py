"""Tests for the Danfoss Air integration setup and polling."""

from datetime import timedelta
import threading
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pydanfossair.commands import ReadCommand
import pytest

from homeassistant.components.danfoss_air import DanfossAir
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from . import setup_integration


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Move past the update throttle and update every entity one at a time."""
    freezer.tick(timedelta(seconds=61))
    for entity_id in hass.states.async_entity_ids():
        await async_update_entity(hass, entity_id)


def _unavailable(hass: HomeAssistant) -> list[str]:
    """Return the entities that are unavailable."""
    return [
        state.entity_id
        for state in hass.states.async_all()
        if state.state == STATE_UNAVAILABLE
    ]


async def test_unavailable_when_connection_lost(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_danfoss_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entities go unavailable when the CCM is unreachable, and recover."""
    await setup_integration(hass)
    await _poll(hass, freezer)
    entity_ids = hass.states.async_entity_ids()
    assert entity_ids
    assert _unavailable(hass) == []

    read_values = mock_danfoss_client.command.side_effect
    mock_danfoss_client.command.side_effect = OSError("No route to host")

    await _poll(hass, freezer)
    assert sorted(_unavailable(hass)) == sorted(entity_ids)
    assert "Lost connection to Danfoss Air CCM module" in caplog.text

    # Only the first failed poll is logged.
    caplog.clear()
    await _poll(hass, freezer)
    assert sorted(_unavailable(hass)) == sorted(entity_ids)
    assert "Lost connection" not in caplog.text

    mock_danfoss_client.command.side_effect = read_values

    await _poll(hass, freezer)
    assert _unavailable(hass) == []
    assert "Connection to Danfoss Air CCM module restored" in caplog.text


@pytest.mark.parametrize(
    ("available_before", "fetch_fails", "expected"),
    [
        pytest.param(True, False, (True, True), id="fetch"),
        pytest.param(True, True, (False, None), id="connection-lost"),
        pytest.param(False, False, (True, True), id="connection-restored"),
    ],
)
def test_overlapping_update_waits_for_fetch(
    mock_danfoss_client: MagicMock,
    available_before: bool,
    fetch_fails: bool,
    expected: tuple[bool, bool | None],
) -> None:
    """Test an update that arrives during a fetch sees the outcome of that fetch."""
    read_values = mock_danfoss_client.command.side_effect
    fetch_started = threading.Event()
    release_fetch = threading.Event()

    def slow_command(command: ReadCommand) -> float | bool:
        fetch_started.set()
        assert release_fetch.wait(5)
        if fetch_fails:
            raise OSError("timed out")
        return read_values(command)

    mock_danfoss_client.command.side_effect = slow_command
    danfoss_air = DanfossAir("192.0.2.1")
    danfoss_air.available = available_before

    first = threading.Thread(target=danfoss_air.update)
    first.start()
    assert fetch_started.wait(5)

    seen: list[tuple[bool, bool | None]] = []

    def second_update() -> None:
        danfoss_air.update()
        seen.append(
            (
                danfoss_air.available,
                danfoss_air.get_value(ReadCommand.automatic_bypass),
            )
        )

    second = threading.Thread(target=second_update)
    second.start()
    try:
        second.join(0.2)
        waited = second.is_alive()
    finally:
        release_fetch.set()
        first.join(5)
        second.join(5)

    assert waited, "second update did not wait for the running fetch"
    assert seen == [expected]
    # The second caller reused the first fetch instead of fetching again.
    fetches = [
        call
        for call in mock_danfoss_client.command.call_args_list
        if call.args[0] is ReadCommand.exhaustTemperature
    ]
    assert len(fetches) == 1
