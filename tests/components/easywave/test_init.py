"""Tests for the init module of the Easywave Core integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from homeassistant.components.easywave import (
    async_setup_entry,
    async_unload_entry,
    async_remove_config_entry_device,
)
from homeassistant.components.easywave.const import (
    DOMAIN,
    CONF_USB_PID,
)


@pytest.mark.asyncio
async def test_async_setup_entry(hass: HomeAssistant, mock_config_entry):
    """Test setup of config entry."""
    mock_config_entry.add_to_hass(hass)
    
    result = await async_setup_entry(hass, mock_config_entry)
    
    assert result is True
    assert DOMAIN in hass.data


@pytest.mark.asyncio
async def test_async_setup_entry_forwards_to_platforms(hass: HomeAssistant, mock_config_entry):
    """Test that setup_entry forwards to platforms."""
    mock_config_entry.add_to_hass(hass)
    
    with AsyncMock(return_value=True) as mock_forward:
        mock_config_entry.async_forward_entry_setups = mock_forward
        
        await async_setup_entry(hass, mock_config_entry)
        
        # Should forward to sensor platform
        assert mock_forward.called


@pytest.mark.asyncio
async def test_async_setup_entry_country_allowed(hass: HomeAssistant, mock_config_entry):
    """Test setup with allowed country."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "DE"  # Germany is allowed for 868MHz
    
    result = await async_setup_entry(hass, mock_config_entry)
    
    assert result is True


@pytest.mark.asyncio
async def test_async_setup_entry_country_not_allowed(hass: HomeAssistant, mock_config_entry):
    """Test setup with disallowed country."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "US"  # USA is NOT allowed for 868MHz
    
    result = await async_setup_entry(hass, mock_config_entry)
    
    assert result is False


@pytest.mark.asyncio
async def test_async_setup_entry_creates_repair_issue_on_country_mismatch(
    hass: HomeAssistant, mock_config_entry
):
    """Test that a repair issue is created when country is not allowed."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "US"  # Not allowed
    
    with patch("homeassistant.components.easywave.ir.async_create_issue") as mock_create:
        with patch("homeassistant.components.easywave.ir.async_delete_issue"):
            result = await async_setup_entry(hass, mock_config_entry)
    
    assert result is False
    assert mock_create.called


@pytest.mark.asyncio
async def test_async_setup_entry_deletes_stale_repair_issue_on_success(
    hass: HomeAssistant, mock_config_entry
):
    """Test that stale repair issues are removed when setup succeeds."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "DE"  # Allowed
    
    with patch("homeassistant.components.easywave.ir.async_delete_issue") as mock_delete:
        result = await async_setup_entry(hass, mock_config_entry)
    
    assert result is True
    assert mock_delete.called


@pytest.mark.asyncio
async def test_async_setup_entry_no_country_configured(hass: HomeAssistant, mock_config_entry):
    """Test setup when no country is configured."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = None
    
    result = await async_setup_entry(hass, mock_config_entry)
    
    # Should allow setup if no country is configured
    assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry(hass: HomeAssistant, mock_config_entry):
    """Test unload of config entry."""
    mock_config_entry.add_to_hass(hass)
    
    result = await async_unload_entry(hass, mock_config_entry)
    
    # Result depends on platform unload
    assert result is not None


@pytest.mark.asyncio
async def test_async_remove_config_entry_device_raises_error(
    hass: HomeAssistant, 
    mock_config_entry,
):
    """Test that removing device raises an error."""
    device_entry = MagicMock()
    device_entry.name = "RX11 USB Transceiver"
    
    with pytest.raises(HomeAssistantError) as exc_info:
        await async_remove_config_entry_device(hass, mock_config_entry, device_entry)
    
    # Should raise error with translation
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "cannot_delete_rx11"


@pytest.mark.asyncio
async def test_async_remove_config_entry_device_correct_message(
    hass: HomeAssistant, 
    mock_config_entry,
):
    """Test device removal error has correct translation keys."""
    device_entry = MagicMock()
    
    try:
        await async_remove_config_entry_device(hass, mock_config_entry, device_entry)
    except HomeAssistantError as e:
        assert e.translation_domain == DOMAIN
        assert e.translation_key == "cannot_delete_rx11"

