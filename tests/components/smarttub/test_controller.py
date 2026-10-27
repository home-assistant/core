"""Test the SmartTub polling controller."""

import asyncio
import copy
from unittest.mock import create_autospec, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
import smarttub

from homeassistant.components.climate import ATTR_TEMPERATURE
from homeassistant.components.smarttub.const import MAX_STALE_POLLS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State

from . import trigger_update

FAILURES = [
    pytest.param(TimeoutError, id="timeout"),
    pytest.param(smarttub.APIError, id="api_error"),
]


def _thermostat(hass: HomeAssistant, spa: smarttub.Spa) -> State:
    """Return the state object of the spa's thermostat."""
    state = hass.states.get(f"climate.{spa.brand}_{spa.model}_thermostat")
    assert state is not None
    return state


def _thermostat_state(hass: HomeAssistant, spa: smarttub.Spa) -> str:
    """Return the state of the spa's thermostat."""
    return _thermostat(hass, spa).state


def _set_target_temperature(spa: smarttub.Spa, temperature: float) -> None:
    """Make the next poll of the spa report a new target temperature."""
    status = copy.copy(spa.get_status_full.return_value)
    status.set_temperature = temperature
    spa.get_status_full.return_value = status


@pytest.mark.usefixtures("setup_entry")
async def test_errors_not_fetched_without_error_code(spa: smarttub.Spa) -> None:
    """Test the errors endpoint is not queried while the spa reports no error."""
    spa.get_status_full.assert_awaited_once()
    spa.get_reminders.assert_awaited_once()
    spa.get_errors.assert_not_awaited()


async def test_errors_fetched_with_error_code(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    spa: smarttub.Spa,
    spa_state: smarttub.SpaStateFull,
) -> None:
    """Test the errors endpoint is queried while the spa reports an error."""
    spa_state.error_code = 11

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    spa.get_errors.assert_awaited_once()


@pytest.mark.parametrize("failure", FAILURES)
async def test_failed_poll_keeps_last_data(
    hass: HomeAssistant,
    spa: smarttub.Spa,
    setup_entry: None,
    failure: type[Exception],
) -> None:
    """Test entities stay available through brief outages."""
    spa.get_status_full.side_effect = failure

    for _ in range(MAX_STALE_POLLS):
        await trigger_update(hass)
        assert _thermostat_state(hass, spa) != STATE_UNAVAILABLE


@pytest.mark.parametrize("failure", FAILURES)
async def test_entities_unavailable_after_repeated_failures(
    hass: HomeAssistant,
    spa: smarttub.Spa,
    setup_entry: None,
    failure: type[Exception],
) -> None:
    """Test entities become unavailable once the outage is not brief."""
    spa.get_status_full.side_effect = failure

    for _ in range(MAX_STALE_POLLS + 1):
        await trigger_update(hass)

    assert _thermostat_state(hass, spa) == STATE_UNAVAILABLE


async def test_successful_poll_resets_failure_count(
    hass: HomeAssistant,
    spa: smarttub.Spa,
    spa_state: smarttub.SpaStateFull,
    setup_entry: None,
) -> None:
    """Test only consecutive failures make entities unavailable."""
    for _ in range(MAX_STALE_POLLS + 1):
        spa.get_status_full.side_effect = TimeoutError
        await trigger_update(hass)
        assert _thermostat_state(hass, spa) != STATE_UNAVAILABLE
        spa.get_status_full.side_effect = None
        spa.get_status_full.return_value = spa_state
        await trigger_update(hass)


@pytest.mark.parametrize("failure", FAILURES)
async def test_entities_unavailable_when_first_poll_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    spa: smarttub.Spa,
    failure: type[Exception],
) -> None:
    """Test there is no data to keep when the very first poll fails."""
    spa.get_status_full.side_effect = failure

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert _thermostat_state(hass, spa) == STATE_UNAVAILABLE


@pytest.fixture(name="second_spa")
def mock_second_spa(spa_state: smarttub.SpaStateFull) -> smarttub.Spa:
    """Mock a second spa on the same account, without pumps, lights or sensors."""
    second_state = copy.copy(spa_state)
    second_state.pumps = []
    second_state.lights = []
    second_state.sensors = []

    second_spa = create_autospec(smarttub.Spa, instance=True)
    second_spa.id = "mockspa2"
    second_spa.brand = "mockbrand2"
    second_spa.model = "mockmodel2"
    second_spa.get_status_full.return_value = second_state
    second_spa.get_reminders.return_value = []
    second_spa.get_errors.return_value = []
    return second_spa


@pytest.fixture(name="two_spa_account")
def mock_two_spa_account(
    account: smarttub.Account, spa: smarttub.Spa, second_spa: smarttub.Spa
) -> smarttub.Account:
    """Put both spas on the account."""
    account.get_spas.return_value = [spa, second_spa]
    return account


@pytest.mark.usefixtures("two_spa_account")
async def test_spas_are_polled_concurrently(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    spa: smarttub.Spa,
    second_spa: smarttub.Spa,
) -> None:
    """Test a slow spa does not delay polling the others."""
    barrier = asyncio.Barrier(2)

    def wait_for_other_spa(spa_to_wrap: smarttub.Spa) -> None:
        original = spa_to_wrap.get_status_full.return_value

        async def get_status_full() -> smarttub.SpaStateFull:
            await barrier.wait()
            return original

        spa_to_wrap.get_status_full.side_effect = get_status_full

    wait_for_other_spa(spa)
    wait_for_other_spa(second_spa)

    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.smarttub.controller.POLLING_TIMEOUT", 1):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert _thermostat_state(hass, spa) != STATE_UNAVAILABLE
    assert _thermostat_state(hass, second_spa) != STATE_UNAVAILABLE


@pytest.mark.usefixtures("two_spa_account")
async def test_failed_spa_does_not_discard_other_spas(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    spa: smarttub.Spa,
    second_spa: smarttub.Spa,
) -> None:
    """Test a spa failing a poll keeps its last data while the others update."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    _set_target_temperature(spa, 40)
    _set_target_temperature(second_spa, 40)
    second_spa.get_status_full.side_effect = TimeoutError
    await trigger_update(hass)

    assert _thermostat(hass, spa).attributes[ATTR_TEMPERATURE] == 40
    second_thermostat = _thermostat(hass, second_spa)
    assert second_thermostat.state != STATE_UNAVAILABLE
    assert second_thermostat.attributes[ATTR_TEMPERATURE] == 39


@pytest.mark.usefixtures("two_spa_account")
async def test_last_data_is_kept_for_each_spa_through_an_aggregate_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    spa: smarttub.Spa,
    second_spa: smarttub.Spa,
) -> None:
    """Test a spa's last data is not older than its last successful poll."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    spa.get_status_full.side_effect = TimeoutError
    for temperature in range(30, 30 + MAX_STALE_POLLS + 1):
        _set_target_temperature(second_spa, temperature)
        await trigger_update(hass)
    assert _thermostat_state(hass, second_spa) == STATE_UNAVAILABLE

    spa.get_status_full.side_effect = None
    second_spa.get_status_full.side_effect = TimeoutError
    await trigger_update(hass)

    second_thermostat = _thermostat(hass, second_spa)
    assert second_thermostat.state != STATE_UNAVAILABLE
    assert second_thermostat.attributes[ATTR_TEMPERATURE] == temperature
