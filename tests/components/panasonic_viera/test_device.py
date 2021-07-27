"""Test the Panasonic Viera device."""

from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from homeassistant.components.panasonic_viera import Device
from homeassistant.const import STATE_OFF


async def test_device_handle_httperror(hass, mock_remote):
    """Test device handle httperror as Off."""

    device = Device(hass, "1.0.0.0", 1)

    # simulate http badrequest
    mock_remote.get_mute = Mock(side_effect=HTTPError("", 400, "", None, None))

    await device.async_create_remote_control(True)
    await hass.async_block_till_done()

    assert device.state == STATE_OFF
    assert device.available is True


async def test_device_handle_urlerror(hass, mock_remote):
    """Test device handle urlerror as Unavailable."""

    device = Device(hass, "1.0.0.0", 1)

    # simulate timeout error
    mock_remote.get_mute = Mock(side_effect=URLError("", ""))

    await device.async_create_remote_control(True)
    await hass.async_block_till_done()

    assert device.state == STATE_OFF
    assert device.available is False
