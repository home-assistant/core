"""Test Axis component setup process."""
from unittest.mock import Mock, patch

from homeassistant.components import axis
from homeassistant.setup import async_setup_component

from .test_device import MAC, setup_axis_integration

from tests.async_mock import AsyncMock
from tests.common import MockConfigEntry


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
    config_entry = MockConfigEntry(
        domain=axis.DOMAIN, data={axis.CONF_MAC: "0123"}, version=2
    )
    config_entry.add_to_hass(hass)

    mock_device = Mock()
    mock_device.async_setup = AsyncMock(return_value=False)

    with patch.object(axis, "AxisNetworkDevice") as mock_device_class:
        mock_device_class.return_value = mock_device

        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert not hass.data[axis.DOMAIN]


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    device = await setup_axis_integration(hass)
    assert hass.data[axis.DOMAIN]

    assert await hass.config_entries.async_unload(device.config_entry.entry_id)
    assert not hass.data[axis.DOMAIN]


async def test_populate_options(hass):
    """Test successful populate options."""
    device = await setup_axis_integration(hass, options=None)

    assert device.config_entry.options == {
        axis.CONF_CAMERA: True,
        axis.CONF_EVENTS: True,
        axis.CONF_TRIGGER_TIME: axis.DEFAULT_TRIGGER_TIME,
    }


async def test_migrate_entry(hass):
    """Test successful migration of entry data."""
    legacy_config = {
        axis.CONF_DEVICE: {
            axis.CONF_HOST: "1.2.3.4",
            axis.CONF_USERNAME: "username",
            axis.CONF_PASSWORD: "password",
            axis.CONF_PORT: 80,
        },
        axis.CONF_MAC: "mac",
        axis.device.CONF_MODEL: "model",
        axis.device.CONF_NAME: "name",
    }
    entry = MockConfigEntry(domain=axis.DOMAIN, data=legacy_config)

    assert entry.data == legacy_config
    assert entry.version == 1

    await entry.async_migrate(hass)

    assert entry.data == {
        axis.CONF_DEVICE: {
            axis.CONF_HOST: "1.2.3.4",
            axis.CONF_USERNAME: "username",
            axis.CONF_PASSWORD: "password",
            axis.CONF_PORT: 80,
        },
        axis.CONF_HOST: "1.2.3.4",
        axis.CONF_USERNAME: "username",
        axis.CONF_PASSWORD: "password",
        axis.CONF_PORT: 80,
        axis.CONF_MAC: "mac",
        axis.device.CONF_MODEL: "model",
        axis.device.CONF_NAME: "name",
    }
    assert entry.version == 2
