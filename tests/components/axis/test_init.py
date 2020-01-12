"""Test Axis component setup process."""
from unittest.mock import Mock, patch

from homeassistant.components import axis
from homeassistant.setup import async_setup_component

from .test_device import MAC, setup_axis_integration

from tests.common import MockConfigEntry, mock_coro


async def test_setup_device_already_configured(hass):
    """Test already configured device does not configure a second."""
    with patch.object(hass, "config_entries") as mock_config_entries:

        assert await async_setup_component(
            hass,
            axis.DOMAIN,
            {axis.DOMAIN: {"device_name": {axis.config_flow.CONF_HOST: "1.2.3.4"}}},
        )

    assert not mock_config_entries.flow.mock_calls


async def test_setup_no_config(hass):
    """Test setup without configuration."""
    assert await async_setup_component(hass, axis.DOMAIN, {})
    assert axis.DOMAIN not in hass.data


async def test_setup_entry(hass):
    """Test successful setup of entry."""
    await setup_axis_integration(hass)
    assert len(hass.data[axis.DOMAIN]) == 1
    assert MAC in hass.data[axis.DOMAIN]


async def test_setup_entry_fails(hass):
    """Test successful setup of entry."""
    entry = MockConfigEntry(
        domain=axis.DOMAIN, data={axis.device.CONF_MAC: "0123"}, options=True
    )

    mock_device = Mock()
    mock_device.async_setup.return_value = mock_coro(False)

    with patch.object(axis, "AxisNetworkDevice") as mock_device_class:
        mock_device_class.return_value = mock_device

        assert not await axis.async_setup_entry(hass, entry)

    assert not hass.data[axis.DOMAIN]


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    device = await setup_axis_integration(hass)
    assert hass.data[axis.DOMAIN]

    assert await axis.async_unload_entry(hass, device.config_entry)
    assert not hass.data[axis.DOMAIN]


async def test_populate_options(hass):
    """Test successful populate options."""
    entry = MockConfigEntry(domain=axis.DOMAIN, data={"device": {}})
    entry.add_to_hass(hass)

    with patch.object(axis, "get_device", return_value=mock_coro(Mock())):

        await axis.async_populate_options(hass, entry)

    assert entry.options == {
        axis.CONF_CAMERA: True,
        axis.CONF_EVENTS: True,
        axis.CONF_TRIGGER_TIME: axis.DEFAULT_TRIGGER_TIME,
    }
