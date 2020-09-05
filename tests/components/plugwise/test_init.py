"""Tests for the Plugwise Climate integration."""

import asyncio

from Plugwise_Smile.Smile import Smile

from tests.components.plugwise.common import async_init_integration


async def test_smile_unauthorized(hass, mock_smile_unauth):
    """Test failing unauthorization by Smile."""
    assert not await async_init_integration(hass, mock_smile_unauth)


async def test_smile_error(hass, mock_smile_error):
    """Test server error handling by Smile."""
    assert not await async_init_integration(hass, mock_smile_error)


async def test_smile_notconnect(hass, mock_smile_notconnect):
    """Connection failure error handling by Smile."""
    mock_smile_notconnect.connect.return_value = False
    try:
        assert not await async_init_integration(hass, mock_smile_notconnect)
    except Smile.PlugwiseError as exception:
        assert exception is Smile.InvalidAuthentication


async def test_smile_timeout(hass, mock_smile_notconnect):
    """Timeout error handling by Smile."""
    mock_smile_notconnect.connect.side_effect = asyncio.TimeoutError
    try:
        assert not await async_init_integration(hass, mock_smile_notconnect)
    except asyncio.TimeoutError as exception:
        assert exception is asyncio.TimeoutError


async def test_smile_adam_xmlerror(hass, mock_smile_adam):
    """Detect malformed XML by Smile in Adam environment."""
    mock_smile_adam.full_update_device.side_effect = Smile.XMLDataMissingError
    try:
        assert not await async_init_integration(hass, mock_smile_adam)
    except Smile.XMLDataMissingError as exception:
        assert exception is Smile.XMLDataMissingError
