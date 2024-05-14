"""Tests for wemo_device.py."""

import asyncio
from dataclasses import asdict
from datetime import timedelta
from unittest.mock import call, patch

import pytest
from pywemo.exceptions import ActionException, PyWeMoException
from pywemo.subscribe import EVENT_TYPE_LONG_PRESS

from homeassistant import runner
from homeassistant.components.wemo import CONF_DISCOVERY, CONF_STATIC
from homeassistant.components.wemo.const import DOMAIN, WEMO_SUBSCRIPTION_EVENT
from homeassistant.components.wemo.coordinator import Options, async_get_coordinator
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import MOCK_FIRMWARE_VERSION, MOCK_HOST, MOCK_SERIAL_NUMBER

from tests.common import async_fire_time_changed

asyncio.set_event_loop_policy(runner.HassEventLoopPolicy(True))


@pytest.fixture
def pywemo_model():
    """Pywemo LightSwitch models use the switch platform."""
    return "LightSwitchLongPress"


async def test_async_register_device_longpress_fails(
    hass: HomeAssistant, pywemo_device, device_registry: dr.DeviceRegistry
) -> None:
    """Device is still registered if ensure_long_press_virtual_device fails."""
    with patch.object(pywemo_device, "ensure_long_press_virtual_device") as elp:
        elp.side_effect = PyWeMoException
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_DISCOVERY: False,
                    CONF_STATIC: [MOCK_HOST],
                },
            },
        )
        await hass.async_block_till_done()
    device_entries = list(device_registry.devices.values())
    assert len(device_entries) == 1
    device = async_get_coordinator(hass, device_entries[0].id)
    assert device.supports_long_press is False


async def test_long_press_event(
    hass: HomeAssistant, pywemo_registry, wemo_entity
) -> None:
    """Device fires a long press event."""
    device = async_get_coordinator(hass, wemo_entity.device_id)
    got_event = asyncio.Event()
    event_data = {}

    @callback
    def async_event_received(event):
        nonlocal event_data
        event_data = event.data
        got_event.set()

    hass.bus.async_listen_once(WEMO_SUBSCRIPTION_EVENT, async_event_received)

    await hass.async_add_executor_job(
        pywemo_registry.callbacks[device.wemo.name],
        device.wemo,
        EVENT_TYPE_LONG_PRESS,
        "testing_params",
    )

    async with asyncio.timeout(8):
        await got_event.wait()

    assert event_data == {
        "device_id": wemo_entity.device_id,
        "name": device.wemo.name,
        "params": "testing_params",
        "type": EVENT_TYPE_LONG_PRESS,
        "unique_id": device.wemo.serial_number,
    }


async def test_subscription_callback(
    hass: HomeAssistant, pywemo_registry, wemo_entity
) -> None:
    """Device processes a registry subscription callback."""
    device = async_get_coordinator(hass, wemo_entity.device_id)
    device.last_update_success = False

    got_callback = asyncio.Event()

    @callback
    def async_received_callback():
        got_callback.set()

    device.async_add_listener(async_received_callback)

    await hass.async_add_executor_job(
        pywemo_registry.callbacks[device.wemo.name], device.wemo, "", ""
    )

    async with asyncio.timeout(8):
        await got_callback.wait()
    assert device.last_update_success


async def test_subscription_update_action_exception(
    hass: HomeAssistant, pywemo_device, wemo_entity
) -> None:
    """Device handles ActionException on get_state properly."""
    device = async_get_coordinator(hass, wemo_entity.device_id)
    device.last_update_success = True

    pywemo_device.subscription_update.return_value = False
    pywemo_device.get_state.reset_mock()
    pywemo_device.get_state.side_effect = ActionException
    await hass.async_add_executor_job(
        device.subscription_callback, pywemo_device, "", ""
    )
    await hass.async_block_till_done()

    pywemo_device.get_state.assert_called_once_with(True)
    assert device.last_update_success is False
    assert isinstance(device.last_exception, UpdateFailed)


async def test_subscription_update_exception(
    hass: HomeAssistant, pywemo_device, wemo_entity
) -> None:
    """Device handles Exception on get_state properly."""
    device = async_get_coordinator(hass, wemo_entity.device_id)
    device.last_update_success = True

    pywemo_device.subscription_update.return_value = False
    pywemo_device.get_state.reset_mock()
    pywemo_device.get_state.side_effect = Exception
    await hass.async_add_executor_job(
        device.subscription_callback, pywemo_device, "", ""
    )
    await hass.async_block_till_done()

    pywemo_device.get_state.assert_called_once_with(True)
    assert device.last_update_success is False
    assert isinstance(device.last_exception, Exception)


async def test_async_update_data_subscribed(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """No update happens when the device is subscribed."""
    device = async_get_coordinator(hass, wemo_entity.device_id)
    pywemo_registry.is_subscribed.return_value = True
    pywemo_device.get_state.reset_mock()
    await device._async_update_data()
    pywemo_device.get_state.assert_not_called()


async def test_device_info(
    hass: HomeAssistant, wemo_entity, device_registry: dr.DeviceRegistry
) -> None:
    """Verify the DeviceInfo data is set properly."""
    device_entries = list(device_registry.devices.values())

    assert len(device_entries) == 1
    assert device_entries[0].connections == {
        ("upnp", f"uuid:LightSwitch-1_0-{MOCK_SERIAL_NUMBER}")
    }
    assert device_entries[0].manufacturer == "Belkin"
    assert device_entries[0].model == "LightSwitch"
    assert device_entries[0].sw_version == MOCK_FIRMWARE_VERSION


async def test_dli_device_info(
    hass: HomeAssistant, wemo_dli_entity, device_registry: dr.DeviceRegistry
) -> None:
    """Verify the DeviceInfo data for Digital Loggers emulated wemo device."""
    device_entries = list(device_registry.devices.values())

    assert device_entries[0].configuration_url == "http://127.0.0.1"
    assert device_entries[0].identifiers == {(DOMAIN, "123456789")}


async def test_options_enable_subscription_false(
    hass, pywemo_registry, pywemo_device, wemo_entity
):
    """Test setting Options.enable_subscription = False."""
    config_entry = hass.config_entries.async_get_entry(wemo_entity.config_entry_id)
    assert hass.config_entries.async_update_entry(
        config_entry,
        options=asdict(Options(enable_subscription=False, enable_long_press=False)),
    )
    await hass.async_block_till_done()
    pywemo_registry.unregister.assert_called_once_with(pywemo_device)


async def test_options_enable_long_press_false(hass, pywemo_device, wemo_entity):
    """Test setting Options.enable_long_press = False."""
    config_entry = hass.config_entries.async_get_entry(wemo_entity.config_entry_id)
    assert hass.config_entries.async_update_entry(
        config_entry, options=asdict(Options(enable_long_press=False))
    )
    await hass.async_block_till_done()
    pywemo_device.remove_long_press_virtual_device.assert_called_once_with()


class TestInsight:
    """Tests specific to the WeMo Insight device."""

    @pytest.fixture
    def pywemo_model(self):
        """Pywemo Dimmer models use the light platform (WemoDimmer class)."""
        return "Insight"

    @pytest.fixture(name="pywemo_device")
    def pywemo_device_fixture(self, pywemo_device):
        """Fixture for WeMoDevice instances."""
        pywemo_device.insight_params = {
            "currentpower": 1.0,
            "todaymw": 200000000.0,
            "state": 0,
            "onfor": 0,
            "ontoday": 0,
            "ontotal": 0,
            "powerthreshold": 0,
        }
        return pywemo_device

    @pytest.mark.parametrize(
        ("subscribed", "state", "expected_calls"),
        [
            (False, 0, [call(), call(True), call(), call()]),
            (False, 1, [call(), call(True), call(), call()]),
            (True, 0, [call(), call(True), call(), call()]),
            (True, 1, [call(), call(), call()]),
        ],
    )
    async def test_should_poll(
        self,
        hass,
        subscribed,
        state,
        expected_calls,
        wemo_entity,
        pywemo_device,
        pywemo_registry,
    ):
        """Validate the should_poll returns the correct value."""
        pywemo_registry.is_subscribed.return_value = subscribed
        pywemo_device.get_state.reset_mock()
        pywemo_device.get_state.return_value = state
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()
        pywemo_device.get_state.assert_has_calls(expected_calls)
