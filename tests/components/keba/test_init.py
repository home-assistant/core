"""Tests for setting up the KEBA charging station integration."""

from typing import Any
from unittest.mock import MagicMock, call

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.keba.const import DOMAIN, KebaService
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import HOST, async_advance, async_seconds_until_poll, async_settle


async def test_setup(hass: HomeAssistant, setup_keba: MagicMock) -> None:
    """Test setup connects, requests the station's data, then starts polling."""
    setup_keba.setup.assert_awaited_once_with(None)
    # The initial request during setup, then the first poll.
    assert setup_keba.request_data.await_count == 2
    assert hass.services.has_service(DOMAIN, KebaService.REQUEST_DATA)
    assert hass.states.get("sensor.keba_p30_charging_power") is not None


async def test_setup_disables_failsafe_by_default(
    hass: HomeAssistant, setup_keba: MagicMock
) -> None:
    """Test setup switches failsafe off when it is not configured."""
    setup_keba.set_failsafe.assert_awaited_once_with(0, 0, 0)


@pytest.mark.parametrize(
    "keba_config",
    [
        {
            DOMAIN: {
                CONF_HOST: HOST,
                "failsafe": True,
                "failsafe_timeout": 60,
                "failsafe_fallback": 10,
                "failsafe_persist": 1,
            }
        }
    ],
)
async def test_setup_applies_configured_failsafe(
    hass: HomeAssistant, setup_keba: MagicMock
) -> None:
    """Test setup applies the configured failsafe values."""
    setup_keba.set_failsafe.assert_awaited_once_with(60, 10, 1)


@pytest.mark.parametrize(
    "keba_config",
    [{DOMAIN: {CONF_HOST: HOST, "failsafe": True, "failsafe_timeout": 5}}],
)
async def test_setup_failsafe_out_of_range_currently_unchecked(
    hass: HomeAssistant, setup_keba: MagicMock
) -> None:
    """Test an out-of-range failsafe timeout reaches the library unchecked."""
    setup_keba.set_failsafe.assert_awaited_once_with(5, 6, 0)


async def test_setup_unreachable_station_currently_raises(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    freezer: FrozenDateTimeFactory,
    keba_config: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unreachable station fails setup with an unhandled error."""
    mock_keba.setup.side_effect = ConnectionError("no reply")

    assert not await async_setup_component(hass, DOMAIN, keba_config)
    await hass.async_block_till_done()

    assert "Error during setup of component keba" in caplog.text
    assert "Could not find a charging station" not in caplog.text
    mock_keba.request_data.assert_not_awaited()
    await async_advance(hass, freezer, 60)
    mock_keba.request_data.assert_not_awaited()


async def test_setup_without_serial(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    keba_config: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a station that reports a product but no serial number."""
    del keba_data["Serial"]

    assert not await async_setup_component(hass, DOMAIN, keba_config)
    await hass.async_block_till_done()

    assert f"Could not find a charging station at {HOST}" in caplog.text
    mock_keba.set_failsafe.assert_not_awaited()
    assert not hass.services.has_service(DOMAIN, KebaService.REQUEST_DATA)
    await async_advance(hass, freezer, 60)
    assert mock_keba.request_data.await_count == 1


async def test_polls_every_refresh_interval(
    hass: HomeAssistant, setup_keba: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the polling loop requests the station's data every 5 seconds."""
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == 5
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == 5


@pytest.mark.parametrize(
    ("refresh_interval", "expected_delay"),
    [(2, 5), (5, 5), (30, 30)],
)
async def test_refresh_interval_has_a_floor(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    freezer: FrozenDateTimeFactory,
    refresh_interval: int,
    expected_delay: int,
) -> None:
    """Test the polling interval is the configured one, but never under 5 seconds."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_HOST: HOST, "refresh_interval": refresh_interval}}
    )
    await async_settle(hass)

    assert await async_seconds_until_poll(hass, freezer, mock_keba) == expected_delay


async def test_command_switches_to_fast_polling(
    hass: HomeAssistant, setup_keba: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a command polls at once, then four times 2 seconds apart, then every 5."""
    polls_before = setup_keba.request_data.await_count

    await hass.services.async_call(DOMAIN, KebaService.ENABLE, blocking=True)
    await async_settle(hass)

    assert setup_keba.enable.await_args_list == [call(True)]
    assert setup_keba.request_data.await_count == polls_before + 1
    assert [
        await async_seconds_until_poll(hass, freezer, setup_keba) for _ in range(5)
    ] == [2, 2, 2, 2, 5]
