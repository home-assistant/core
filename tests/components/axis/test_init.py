"""Test Axis component setup process."""
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components import axis
from homeassistant.components.axis.const import CONF_MODEL, DOMAIN as AXIS_DOMAIN
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.setup import async_setup_component

from .test_device import MAC, setup_axis_integration

from tests.common import MockConfigEntry


async def test_setup_no_config(hass):
    """Test setup without configuration."""
    assert await async_setup_component(hass, AXIS_DOMAIN, {})
    assert AXIS_DOMAIN not in hass.data


async def test_setup_entry(hass):
    """Test successful setup of entry."""
    await setup_axis_integration(hass)
    assert len(hass.data[AXIS_DOMAIN]) == 1
    assert MAC in hass.data[AXIS_DOMAIN]


async def test_setup_entry_fails(hass):
    """Test successful setup of entry."""
    config_entry = MockConfigEntry(
        domain=AXIS_DOMAIN, data={CONF_MAC: "0123"}, version=2
    )
    config_entry.add_to_hass(hass)

    mock_device = Mock()
    mock_device.async_setup = AsyncMock(return_value=False)

    with patch.object(axis, "AxisNetworkDevice") as mock_device_class:
        mock_device_class.return_value = mock_device

        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert not hass.data[AXIS_DOMAIN]


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    config_entry = await setup_axis_integration(hass)
    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]
    assert hass.data[AXIS_DOMAIN]

    assert await hass.config_entries.async_unload(device.config_entry.entry_id)
    assert not hass.data[AXIS_DOMAIN]


async def test_migrate_entry(hass):
    """Test successful migration of entry data."""
    legacy_config = {
        CONF_DEVICE: {
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 80,
        },
        CONF_MAC: "mac",
        CONF_MODEL: "model",
        CONF_NAME: "name",
    }
    entry = MockConfigEntry(domain=AXIS_DOMAIN, data=legacy_config)

    assert entry.data == legacy_config
    assert entry.version == 1

    await entry.async_migrate(hass)

    assert entry.data == {
        CONF_DEVICE: {
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 80,
        },
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_PORT: 80,
        CONF_MAC: "mac",
        CONF_MODEL: "model",
        CONF_NAME: "name",
    }
    assert entry.version == 2
