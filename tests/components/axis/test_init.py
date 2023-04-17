"""Test Axis component setup process."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components import axis
from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.setup import async_setup_component


async def test_setup_no_config(hass):
    """Test setup without configuration."""
    assert await async_setup_component(hass, AXIS_DOMAIN, {})
    assert AXIS_DOMAIN not in hass.data


async def test_setup_entry(hass, setup_config_entry):
    """Test successful setup of entry."""
    assert len(hass.data[AXIS_DOMAIN]) == 1
    assert setup_config_entry.entry_id in hass.data[AXIS_DOMAIN]


async def test_setup_entry_fails(hass, config_entry):
    """Test successful setup of entry."""
    mock_device = Mock()
    mock_device.async_setup = AsyncMock(return_value=False)

    with patch.object(axis, "AxisNetworkDevice") as mock_device_class:
        mock_device_class.return_value = mock_device

        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert not hass.data[AXIS_DOMAIN]


async def test_unload_entry(hass, setup_config_entry):
    """Test successful unload of entry."""
    assert hass.data[AXIS_DOMAIN]

    assert await hass.config_entries.async_unload(setup_config_entry.entry_id)
    assert not hass.data[AXIS_DOMAIN]


@pytest.mark.parametrize("config_entry_version", [1])
async def test_migrate_entry(hass, config_entry):
    """Test successful migration of entry data."""
    assert config_entry.version == 1

    mock_device = Mock()
    mock_device.async_setup = AsyncMock()
    mock_device.async_update_device_registry = AsyncMock()
    mock_device.api.vapix.light_control = None
    mock_device.api.vapix.params.image_format = None

    with patch.object(axis, "get_axis_device"), patch.object(
        axis, "AxisNetworkDevice"
    ) as mock_device_class:
        mock_device_class.return_value = mock_device

        assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert hass.data[AXIS_DOMAIN]
    assert config_entry.version == 3
