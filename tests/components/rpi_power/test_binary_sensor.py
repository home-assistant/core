"""Tests for rpi_power binary sensor."""
from datetime import timedelta
import logging
from unittest.mock import MagicMock

from homeassistant.components.rpi_power.binary_sensor import (
    DESCRIPTION_NORMALIZED,
    DESCRIPTION_UNDER_VOLTAGE,
)
from homeassistant.components.rpi_power.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
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


async def test_new(hass, caplog):
    """Test new entry."""
    await _async_setup_component(hass, False)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert not any(x.levelno == logging.WARNING for x in caplog.records)


async def test_new_detected(hass, caplog):
    """Test new entry with under voltage detected."""
    mocked_under_voltage = await _async_setup_component(hass, True)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert (
        len(
            [
                x
                for x in caplog.records
                if x.levelno == logging.WARNING
                and x.message == DESCRIPTION_UNDER_VOLTAGE
            ]
        )
        == 1
    )

    # back to normal
    type(mocked_under_voltage).get = MagicMock(return_value=False)
    future = dt_util.utcnow() + timedelta(minutes=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert (
        len(
            [
                x
                for x in caplog.records
                if x.levelno == logging.INFO and x.message == DESCRIPTION_NORMALIZED
            ]
        )
        == 1
    )
