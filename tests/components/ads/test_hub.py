"""Test the ADS hub's connection helpers."""

from datetime import timedelta
import logging
from unittest.mock import MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pyads
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.ads.const import DOMAIN
from homeassistant.components.ads.hub import PROBE_INTERVAL, async_get_hub, connect
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_DEVICE,
    CONF_PORT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.setup import async_setup_component

from . import MockAdsDevice, get_hub, setup_ads_platform
from .const import AMS_NET_ID, IP_ADDRESS, PORT


async def test_async_get_hub_not_loaded(hass: HomeAssistant) -> None:
    """Test a platform set up before the connection is told to retry."""
    with pytest.raises(PlatformNotReady):
        async_get_hub(hass)


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_async_get_hub(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the hub of the loaded entry is returned."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert async_get_hub(hass) is mock_config_entry.runtime_data


@pytest.mark.parametrize(
    "configure_mock",
    [
        pytest.param(
            lambda mock: setattr(
                mock.return_value.read_state,
                "side_effect",
                pyads.ADSError(err_code=1861),
            ),
            id="timeout",
        ),
        pytest.param(
            lambda mock: setattr(mock.return_value.read_state, "return_value", None),
            id="port_closed",
        ),
    ],
)
def test_connect_closes_on_error(
    mock_pyads_connection: MagicMock, configure_mock
) -> None:
    """Test a connection the device does not answer on is closed again."""
    configure_mock(mock_pyads_connection)

    with pytest.raises(pyads.ADSError):
        connect(AMS_NET_ID, PORT, IP_ADDRESS)

    mock_pyads_connection.return_value.close.assert_called_once()


SWITCH_CONFIG = {"adsvar": "GVL.pump", "name": "Pump"}
SWITCH_ID = "switch.pump"
BOOL_TRUE = b"\x01"
BOOL_FALSE = b"\x00"


async def _async_advance(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: MockAdsDevice,
    delta: timedelta,
) -> None:
    """Move the clock on and let the probe or reconnect it triggers finish."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for delivery in device.deliveries:
        await hass.async_add_executor_job(delivery.join)
    await hass.async_block_till_done()


async def _async_setup_switch(hass: HomeAssistant, device: MockAdsDevice) -> MagicMock:
    """Set up a YAML switch that has received its first value."""
    device.values["GVL.pump"] = BOOL_TRUE
    assert await setup_ads_platform(hass, device, SWITCH_DOMAIN, SWITCH_CONFIG)
    assert hass.states.get(SWITCH_ID).state == STATE_ON
    return get_hub(hass)


async def test_lost_connection(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a device that stops answering is dropped, then rebuilt once back.

    A connection the device dropped stays open on this side, so without the
    probe the entities would show their last value forever.
    """
    await _async_setup_switch(hass, mock_ads_device)
    client = mock_pyads_connection.return_value
    client.read_state.return_value = None
    # A device that is gone answers neither the deletions nor the close.
    client.del_device_notification.side_effect = pyads.ADSError(err_code=1861)
    client.close.side_effect = pyads.ADSError(err_code=1861)
    caplog.set_level(logging.INFO)

    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)

    assert hass.states.get(SWITCH_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count("Lost the connection to the ADS device") == 1
    # Expected failures, so they do not show up as errors.
    assert "ERROR" not in caplog.text
    # The notifications go before the connection, and quickly.
    assert client.mock_calls.index(call.set_timeout(100)) < client.mock_calls.index(
        call.del_device_notification(1, 1)
    )
    assert client.mock_calls.index(
        call.del_device_notification(1, 1)
    ) < client.mock_calls.index(call.close())

    # A probe while the connection is down does not run, so it logs nothing.
    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)
    assert caplog.text.count("Lost the connection to the ADS device") == 1

    client.read_state.return_value = (pyads.ADSSTATE_RUN, 0)
    client.close.side_effect = None
    mock_ads_device.values["GVL.pump"] = BOOL_FALSE
    await _async_advance(hass, freezer, mock_ads_device, timedelta(minutes=5))

    assert hass.states.get(SWITCH_ID).state == STATE_OFF
    assert "Reconnected to the ADS device" in caplog.text
    assert client.add_device_notification.call_count == 2


async def test_reconnect_backs_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_pyads_connection: MagicMock,
    mock_create_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test reconnecting checks the device answers first and backs off."""
    await _async_setup_switch(hass, mock_ads_device)
    client = mock_pyads_connection.return_value
    client.read_state.side_effect = pyads.ADSError(err_code=1861)
    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)
    mock_create_connection.reset_mock()
    mock_create_connection.side_effect = TimeoutError("timed out")
    client.open.reset_mock()

    await _async_advance(hass, freezer, mock_ads_device, timedelta(seconds=5))
    assert mock_create_connection.call_count == 1
    # The AMS router would block for minutes on a device that is still away.
    client.open.assert_not_called()

    # The next attempt waits twice as long.
    await _async_advance(hass, freezer, mock_ads_device, timedelta(seconds=5))
    assert mock_create_connection.call_count == 1
    await _async_advance(hass, freezer, mock_ads_device, timedelta(seconds=5))
    assert mock_create_connection.call_count == 2

    # Reachable, but the request still fails: the connection is closed again.
    mock_create_connection.side_effect = None
    client.close.reset_mock()
    await _async_advance(hass, freezer, mock_ads_device, timedelta(seconds=20))
    client.open.assert_called_once()
    client.close.assert_called_once()
    assert hass.states.get(SWITCH_ID).state == STATE_UNAVAILABLE


async def test_plc_stopped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a stopped PLC keeps its subscriptions and shows the latest value once running."""
    await _async_setup_switch(hass, mock_ads_device)
    client = mock_pyads_connection.return_value
    client.read_state.return_value = (pyads.ADSSTATE_STOP, 0)
    caplog.set_level(logging.INFO)

    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)

    assert hass.states.get(SWITCH_ID).state == STATE_UNAVAILABLE
    assert "The ADS device stopped running (ADS state 6)" in caplog.text
    client.del_device_notification.assert_not_called()
    client.close.assert_not_called()

    # Other clients can still write while the PLC is stopped.
    await mock_ads_device.async_push(hass, "GVL.pump", BOOL_FALSE)
    assert hass.states.get(SWITCH_ID).state == STATE_UNAVAILABLE

    client.read_state.return_value = (pyads.ADSSTATE_RUN, 0)
    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)

    assert hass.states.get(SWITCH_ID).state == STATE_OFF
    assert "The ADS device is running again" in caplog.text
    assert client.add_device_notification.call_count == 1


async def test_refused_subscription_retried_on_reconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test a variable the device did not have is subscribed after a reconnect."""
    client = mock_pyads_connection.return_value
    client.add_device_notification.side_effect = pyads.ADSError(err_code=1808)
    assert await setup_ads_platform(hass, mock_ads_device, SWITCH_DOMAIN, SWITCH_CONFIG)
    assert hass.states.get(SWITCH_ID).state == STATE_UNAVAILABLE

    client.read_state.return_value = None
    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)
    # Nothing was registered, so there is nothing to delete.
    client.del_device_notification.assert_not_called()

    # The PLC came back with a program that has the variable.
    client.read_state.return_value = (pyads.ADSSTATE_RUN, 0)
    client.add_device_notification.side_effect = mock_ads_device.add_device_notification
    mock_ads_device.values["GVL.pump"] = BOOL_TRUE
    await _async_advance(hass, freezer, mock_ads_device, timedelta(seconds=5))

    assert hass.states.get(SWITCH_ID).state == STATE_ON


async def test_reconnect_to_a_stopped_plc(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test reconnecting to a PLC that is not running yet keeps entities unavailable."""
    await _async_setup_switch(hass, mock_ads_device)
    client = mock_pyads_connection.return_value
    client.read_state.return_value = None
    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)

    client.read_state.return_value = (pyads.ADSSTATE_STOP, 0)
    await _async_advance(hass, freezer, mock_ads_device, timedelta(seconds=5))
    assert hass.states.get(SWITCH_ID).state == STATE_UNAVAILABLE

    client.read_state.return_value = (pyads.ADSSTATE_RUN, 0)
    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)
    assert hass.states.get(SWITCH_ID).state == STATE_ON


async def test_unload_stops_monitoring(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test an unloaded entry neither probes nor reconnects."""
    await _async_setup_switch(hass, mock_ads_device)
    client = mock_pyads_connection.return_value
    client.read_state.return_value = None
    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)
    (entry,) = hass.config_entries.async_entries(DOMAIN)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    client.open.reset_mock()
    client.read_state.reset_mock()
    client.close.reset_mock()

    await _async_advance(hass, freezer, mock_ads_device, timedelta(minutes=10))

    client.open.assert_not_called()
    client.read_state.assert_not_called()
    # The drop already closed the connection.
    client.close.assert_not_called()


async def test_probe_skipped_while_one_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test a slow probe is not started a second time."""
    hub = await _async_setup_switch(hass, mock_ads_device)
    client = mock_pyads_connection.return_value
    client.read_state.reset_mock()
    hub._probing = True

    await _async_advance(hass, freezer, mock_ads_device, PROBE_INTERVAL)

    client.read_state.assert_not_called()


async def test_platform_waits_for_the_import(
    hass: HomeAssistant,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML platform waits for the imported entry instead of retrying."""
    mock_ads_device.values["GVL.pump"] = b"\x01"

    assert await setup_ads_platform(
        hass,
        mock_ads_device,
        SWITCH_DOMAIN,
        {"adsvar": "GVL.pump", "name": "Pump"},
    )

    assert hass.states.get("switch.pump").state == STATE_ON
    assert "not ready yet" not in caplog.text


async def test_platform_gives_up_without_an_entry(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a YAML platform retries on its own when no entry ever sets up."""
    with patch("homeassistant.components.ads.hub.HUB_WAIT_TIMEOUT", 0):
        assert await async_setup_component(
            hass,
            SWITCH_DOMAIN,
            {
                DOMAIN: {CONF_DEVICE: "bad", CONF_PORT: PORT},
                SWITCH_DOMAIN: {
                    "platform": DOMAIN,
                    "adsvar": "GVL.pump",
                    "name": "Pump",
                },
            },
        )
        await hass.async_block_till_done()

    assert hass.states.get("switch.pump") is None
    assert "The ADS connection is not set up" in caplog.text
