"""Test the ThermoPro button platform."""

from datetime import datetime, timedelta
import time

import pytest
from thermopro_ble import ThermoProDevice

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import TP357_SERVICE_INFO, TP358_SERVICE_INFO

from tests.common import async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


@pytest.mark.usefixtures("setup_thermopro")
async def test_buttons_tp357(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    assert not hass.states.async_all()
    assert not hass.states.get("button.tp358_4221_set_date_time")
    inject_bluetooth_service_info(hass, TP357_SERVICE_INFO)
    await hass.async_block_till_done()
    assert not hass.states.get("button.tp358_4221_set_date_time")


@pytest.mark.usefixtures("setup_thermopro")
async def test_buttons_tp358_discovery(hass: HomeAssistant) -> None:
    """Test discovery of device with button."""
    assert not hass.states.async_all()
    assert not hass.states.get("button.tp358_4221_set_date_time")
    inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
    await hass.async_block_till_done()

    button = hass.states.get("button.tp358_4221_set_date_time")
    assert button is not None
    assert button.state == STATE_UNKNOWN


@pytest.mark.usefixtures("setup_thermopro")
async def test_buttons_tp358_unavailable(hass: HomeAssistant) -> None:
    """Test tp358 set date&time button goes to unavailability."""
    start_monotonic = time.monotonic()
    assert not hass.states.async_all()
    assert not hass.states.get("button.tp358_4221_set_date_time")
    inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
    await hass.async_block_till_done()

    button = hass.states.get("button.tp358_4221_set_date_time")
    assert button is not None
    assert button.state == STATE_UNKNOWN

    # Fast-forward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 15

    with patch_bluetooth_time(monotonic_now), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 15),
        )
        await hass.async_block_till_done()

    button = hass.states.get("button.tp358_4221_set_date_time")

    assert button.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("setup_thermopro")
async def test_buttons_tp358_reavailable(hass: HomeAssistant) -> None:
    """Test TP358/TP393 set date&time button goes to unavailablity and recovers."""
    start_monotonic = time.monotonic()
    assert not hass.states.async_all()
    assert not hass.states.get("button.tp358_4221_set_date_time")
    inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
    await hass.async_block_till_done()

    button = hass.states.get("button.tp358_4221_set_date_time")
    assert button is not None
    assert button.state == STATE_UNKNOWN

    # Fast-forward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 15

    with patch_bluetooth_time(monotonic_now), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 15),
        )
        await hass.async_block_till_done()

        button = hass.states.get("button.tp358_4221_set_date_time")

        assert button.state == STATE_UNAVAILABLE

        inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
        await hass.async_block_till_done()

        button = hass.states.get("button.tp358_4221_set_date_time")

        assert button.state == STATE_UNKNOWN


@pytest.mark.usefixtures("setup_thermopro")
async def test_buttons_tp358_press(
    hass: HomeAssistant, mock_now: datetime, mock_thermoprodevice: ThermoProDevice
) -> None:
    """Test TP358/TP393 set date&time button press."""
    assert not hass.states.async_all()
    assert not hass.states.get("button.tp358_4221_set_date_time")
    inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
    await hass.async_block_till_done()
    assert hass.states.get("button.tp358_4221_set_date_time")

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: "button.tp358_4221_set_date_time"},
        blocking=True,
    )

    mock_thermoprodevice.set_datetime.assert_awaited_once_with(mock_now, am_pm=False)

    button_state = hass.states.get("button.tp358_4221_set_date_time")
    assert button_state.state != STATE_UNKNOWN
