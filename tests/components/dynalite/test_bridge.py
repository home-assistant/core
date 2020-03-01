"""Test Dynalite bridge."""

from asynctest import CoroutineMock, Mock, call, patch
from dynalite_devices_lib.const import CONF_ALL
import pytest

from homeassistant.components import dynalite

from tests.common import MockConfigEntry


@pytest.fixture
def dyn_bridge():
    """Define a basic mock bridge."""
    hass = Mock()
    host = "1.2.3.4"
    bridge = dynalite.DynaliteBridge(hass, {dynalite.CONF_HOST: host})
    return bridge


async def test_update_device(dyn_bridge):
    """Test a successful setup."""
    async_dispatch = Mock()

    with patch(
        "homeassistant.components.dynalite.bridge.async_dispatcher_send", async_dispatch
    ):
        dyn_bridge.update_device(CONF_ALL)
        async_dispatch.assert_called_once()
        assert async_dispatch.mock_calls[0] == call(
            dyn_bridge.hass, f"dynalite-update-{dyn_bridge.host}"
        )
        async_dispatch.reset_mock()
        device = Mock
        device.unique_id = "abcdef"
        dyn_bridge.update_device(device)
        async_dispatch.assert_called_once()
        assert async_dispatch.mock_calls[0] == call(
            dyn_bridge.hass, f"dynalite-update-{dyn_bridge.host}-{device.unique_id}"
        )


async def test_add_devices_then_register(hass, dyn_bridge):
    """Test that add_devices work."""
    host = "1.2.3.4"
    entry = MockConfigEntry(domain=dynalite.DOMAIN, data={dynalite.CONF_HOST: host})
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices"
    ) as mock_dyn_dev:
        mock_dyn_dev().async_setup = CoroutineMock(return_value=True)
        assert await hass.config_entries.async_setup(entry.entry_id)
        # Not waiting so it add the devices before registration
        new_device_func = mock_dyn_dev.mock_calls[1][2]["newDeviceFunc"]
    # Now with devices
    device1 = Mock()
    device1.category = "light"
    device1.name = "NAME"
    device2 = Mock()
    device2.category = "switch"
    new_device_func([device1, device2])
    await hass.async_block_till_done()
    assert hass.states.get("light.name")


async def test_register_then_add_devices(hass, dyn_bridge):
    """Test that add_devices work after register_add_entities."""
    host = "1.2.3.4"
    entry = MockConfigEntry(domain=dynalite.DOMAIN, data={dynalite.CONF_HOST: host})
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices"
    ) as mock_dyn_dev:
        mock_dyn_dev().async_setup = CoroutineMock(return_value=True)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        new_device_func = mock_dyn_dev.mock_calls[1][2]["newDeviceFunc"]
    # Now with devices
    device1 = Mock()
    device1.category = "light"
    device1.name = "NAME"
    device2 = Mock()
    device2.category = "switch"
    new_device_func([device1, device2])
    await hass.async_block_till_done()
    assert hass.states.get("light.name")
