"""Tests for rpi_power binary sensor."""

from datetime import timedelta
import logging
from unittest.mock import MagicMock

import pytest

from homeassistant.components.rpi_power import binary_sensor
from homeassistant.components.rpi_power.binary_sensor import (
    DESCRIPTION_NORMALIZED,
    DESCRIPTION_UNDER_VOLTAGE,
)
from homeassistant.components.rpi_power.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, patch

ENTITY_ID = "binary_sensor.rpi_power_status"

MODULE = "homeassistant.components.rpi_power.binary_sensor.new_under_voltage"


async def _async_setup_component(hass, detected):
    mocked_under_voltage = MagicMock()
    type(mocked_under_voltage).get = MagicMock(return_value=detected)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    with patch(MODULE, return_value=mocked_under_voltage):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
    return mocked_under_voltage


async def test_new(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test new entry."""
    await _async_setup_component(hass, False)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert not any(x.levelno == logging.WARNING for x in caplog.records)


async def test_new_detected(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test new entry with under voltage detected."""
    mocked_under_voltage = await _async_setup_component(hass, True)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert (
        binary_sensor.__name__,
        logging.WARNING,
        DESCRIPTION_UNDER_VOLTAGE,
    ) in caplog.record_tuples

    # back to normal
    type(mocked_under_voltage).get = MagicMock(return_value=False)
    future = dt_util.utcnow() + timedelta(minutes=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert (
        binary_sensor.__name__,
        logging.INFO,
        DESCRIPTION_NORMALIZED,
    ) in caplog.record_tuples
