"""Tests for the Lutron Caseta integration."""

from unittest.mock import patch

import pytest

from homeassistant.components import lutron_caseta
from homeassistant.components.lutron_caseta.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MockBridge, async_setup_integration, make_mock_entry


@pytest.mark.parametrize(
    ("constant", "message", "timeout_during_connect", "timeout_during_configure"),
    [
        ("CONNECT_TIMEOUT", "Timed out on connect", True, False),
        ("CONFIGURE_TIMEOUT", "Timed out on configure", False, True),
    ],
)
async def test_timeout_during_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    constant: str,
    message: str,
    timeout_during_connect: bool,
    timeout_during_configure: bool,
) -> None:
    """Test a timeout during setup."""
    mock_entry = make_mock_entry()
    mock_entry.add_to_hass(hass)
    with patch.object(lutron_caseta, constant, 0.001):
        await async_setup_integration(
            hass,
            MockBridge,
            config_entry_id=mock_entry.entry_id,
            timeout_during_connect=timeout_during_connect,
            timeout_during_configure=timeout_during_configure,
        )
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
    assert f"{message} for 1.1.1.1" in caplog.text


async def test_cannot_connect(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test failing to connect."""
    mock_entry = make_mock_entry()
    mock_entry.add_to_hass(hass)
    await async_setup_integration(
        hass, MockBridge, config_entry_id=mock_entry.entry_id, can_connect=False
    )
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Connection failed to 1.1.1.1" in caplog.text


async def test_keypad_device_via_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test the keypad device is linked to the bridge device via via_device_id."""
    mock_entry = await async_setup_integration(hass, MockBridge)

    bridge_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, 1234), mock_entry.entry_id
    )
    keypad_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, 66286451), mock_entry.entry_id
    )

    assert bridge_device is not None
    assert keypad_device is not None
    assert keypad_device.via_device_id == bridge_device.id
    assert bridge_device.via_device_id is None
