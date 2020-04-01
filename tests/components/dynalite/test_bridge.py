"""Test Dynalite bridge."""

from asynctest import CoroutineMock, Mock, patch
from dynalite_devices_lib.const import CONF_ALL

from homeassistant.components import dynalite
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from tests.common import MockConfigEntry


async def test_update_device(hass):
    """Test that update works."""
    host = "1.2.3.4"
    entry = MockConfigEntry(domain=dynalite.DOMAIN, data={dynalite.CONF_HOST: host})
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices"
    ) as mock_dyn_dev:
        mock_dyn_dev().async_setup = CoroutineMock(return_value=True)
        assert await hass.config_entries.async_setup(entry.entry_id)
        # Not waiting so it add the devices before registration
        update_device_func = mock_dyn_dev.mock_calls[1][2]["update_device_func"]
    device = Mock()
    device.unique_id = "abcdef"
    wide_func = Mock()
    async_dispatcher_connect(hass, f"dynalite-update-{host}", wide_func)
    specific_func = Mock()
    async_dispatcher_connect(
        hass, f"dynalite-update-{host}-{device.unique_id}", specific_func
    )
    update_device_func(CONF_ALL)
    await hass.async_block_till_done()
    wide_func.assert_called_once()
    specific_func.assert_not_called()
    update_device_func(device)
    await hass.async_block_till_done()
    wide_func.assert_called_once()
    specific_func.assert_called_once()


async def test_add_devices_then_register(hass):
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
        new_device_func = mock_dyn_dev.mock_calls[1][2]["new_device_func"]
    # Now with devices
    device1 = Mock()
    device1.category = "light"
    device1.name = "NAME"
    device1.unique_id = "unique1"
    device2 = Mock()
    device2.category = "switch"
    device2.name = "NAME2"
    device2.unique_id = "unique2"
    new_device_func([device1, device2])
    await hass.async_block_till_done()
    assert hass.states.get("light.name")


async def test_register_then_add_devices(hass):
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
        new_device_func = mock_dyn_dev.mock_calls[1][2]["new_device_func"]
    # Now with devices
    device1 = Mock()
    device1.category = "light"
    device1.name = "NAME"
    device1.unique_id = "unique1"
    device2 = Mock()
    device2.category = "switch"
    device2.name = "NAME2"
    device2.unique_id = "unique2"
    new_device_func([device1, device2])
    await hass.async_block_till_done()
    assert hass.states.get("light.name")
