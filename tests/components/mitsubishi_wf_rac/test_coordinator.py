"""Test the Mitsubishi WF-RAC coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pywfrac import WfRacConnectionError

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "climate.living_room"
POLL = timedelta(seconds=60)


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, polls: int):
    for _ in range(polls):
        freezer.tick(POLL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


async def test_a_missed_poll_does_not_go_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The module reassociates with the WiFi about once an hour on its own.

    Going unavailable on the first missed poll would report an outage every
    hour that nobody can act on, so the retry limit has to be spent first.
    """
    mock_repository.get_aircon_stats.side_effect = WfRacConnectionError("no route")

    await _advance(hass, freezer, 2)
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    await _advance(hass, freezer, 1)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_the_airco_comes_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    aircon_stat: dict,
    init_integration: MockConfigEntry,
) -> None:
    """One good poll is enough to be available again."""
    mock_repository.get_aircon_stats.side_effect = WfRacConnectionError("no route")
    await _advance(hass, freezer, 3)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_repository.get_aircon_stats.side_effect = None
    mock_repository.get_aircon_stats.return_value = aircon_stat
    await _advance(hass, freezer, 1)

    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


async def test_an_evicted_account_re_registers_itself(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Register again after being evicted from the account table.

    Opening the manufacturer's app can push Home Assistant out of it. An
    evicted account still answers, so the failure is answered by registering
    again rather than by waiting.
    """
    mock_repository.update_account_info.reset_mock()
    mock_repository.get_aircon_stats.side_effect = KeyError("airconStat")

    await _advance(hass, freezer, 1)

    mock_repository.update_account_info.assert_awaited()


async def test_an_unreachable_airco_does_not_re_register(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Do not re-register over an outage.

    Registering cannot succeed over a connection that is not there, so a plain
    outage must not spend a request on it.
    """
    mock_repository.update_account_info.reset_mock()
    mock_repository.get_aircon_stats.side_effect = WfRacConnectionError("no route")

    await _advance(hass, freezer, 1)

    mock_repository.update_account_info.assert_not_awaited()
