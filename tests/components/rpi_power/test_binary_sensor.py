"""Tests for rpi_power binary sensor."""
from datetime import timedelta
import logging

from homeassistant.components.rpi_power import DOMAIN
from homeassistant.components.rpi_power.binary_sensor import SYSFILE, SYSFILE_LEGACY
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MagicMock, async_fire_time_changed, patch

ENTITY_ID = "binary_sensor.rpi_power_status"


def _mocked_isfile(sysfile, sysfile_legacy):
    def _isfile(file):
        if sysfile and file == SYSFILE:
            return True
        if sysfile_legacy and file == SYSFILE_LEGACY:
            return True
        return False

    return _isfile


def _mocked_open(detected):
    def _open(file):
        def _read():
            if file == SYSFILE:
                return "1\n" if detected else "0\n"
            elif file == SYSFILE_LEGACY:
                return "50005\n" if detected else "0\n"
            assert False

        file_obj = MagicMock()
        type(file_obj).read = MagicMock(side_effect=_read)
        return file_obj

    return MagicMock(side_effect=_open)


def _patch_isfile(sysfile, sysfile_legacy):
    return patch(
        "homeassistant.components.rpi_power.binary_sensor.os.path.isfile",
        side_effect=_mocked_isfile(sysfile, sysfile_legacy),
    )


def _patch_open(side_effect):
    return patch(
        "homeassistant.components.rpi_power.binary_sensor.open", side_effect=side_effect
    )


async def _async_setup_component(hass, sysfile, sysfile_legacy, detected):
    mocked_open = _mocked_open(detected)
    future = dt_util.utcnow() + timedelta(minutes=1)
    with _patch_isfile(sysfile, sysfile_legacy), _patch_open(mocked_open):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
    mocked_open.assert_called_once_with(SYSFILE if sysfile else SYSFILE_LEGACY)


async def test_not_pi(hass, caplog):
    """Test set up on an non-pi device."""
    with _patch_isfile(False, False):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
    assert len([x for x in caplog.records if x.levelno == logging.CRITICAL]) == 1


async def test_new(hass, caplog):
    """Test new entry."""
    await _async_setup_component(hass, True, True, False)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert not any(x.levelno == logging.WARNING for x in caplog.records)


async def test_legacy(hass, caplog):
    """Test legacy entry."""
    await _async_setup_component(hass, False, True, False)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert not any(x.levelno == logging.WARNING for x in caplog.records)


async def test_new_detected(hass, caplog):
    """Test new entry with under voltage detected."""
    await _async_setup_component(hass, True, True, True)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert len([x for x in caplog.records if x.levelno == logging.WARNING]) == 1

    # back to normal
    mocked_open = _mocked_open(False)
    future = dt_util.utcnow() + timedelta(minutes=1)
    with _patch_open(mocked_open):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert len([x for x in caplog.records if x.levelno == logging.WARNING]) == 2


async def test_legacy_detected(hass, caplog):
    """Test legacy entry with under voltage detected."""
    await _async_setup_component(hass, False, True, True)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert len([x for x in caplog.records if x.levelno == logging.WARNING]) == 1
