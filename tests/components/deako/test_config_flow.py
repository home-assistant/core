"""Tests for the deako component config flow."""
from unittest.mock import patch

from pydeako.discover import DevicesNotFoundException
import pytest

from homeassistant.components.deako.config_flow import _async_has_devices
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_deako_async_has_devices(
    hass: HomeAssistant,
    mock_async_zeroconf: None,
) -> None:
    """Test successful device discovery."""

    with patch(
        "homeassistant.components.deako.config_flow.DeakoDiscoverer", autospec=True
    ) as mock_discoverer:
        ret = await _async_has_devices(hass)

        assert ret
        mock_discoverer.assert_called_once()
        mock_discoverer.return_value.get_address.assert_called_once()


@pytest.mark.asyncio
async def test_deako_async_has_devices_error(
    hass: HomeAssistant,
    mock_async_zeroconf: None,
) -> None:
    """Test successful device discovery."""

    with patch(
        "homeassistant.components.deako.config_flow.DeakoDiscoverer", autospec=True
    ) as mock_discoverer:
        mock_discoverer.return_value.get_address.side_effect = (
            DevicesNotFoundException()
        )
        ret = await _async_has_devices(hass)

        assert not ret
        mock_discoverer.assert_called_once()
        mock_discoverer.return_value.get_address.assert_called_once()
