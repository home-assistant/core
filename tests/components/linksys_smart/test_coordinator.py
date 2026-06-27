"""Tests for the Linksys coordinator."""

from unittest.mock import AsyncMock

from jnap import (
    GetDevicesResponse,
    JNAPClient,
    JNAPDevice,
    JNAPError,
    JNAPUnauthorizedError,
)
import pytest

from homeassistant.components.linksys_smart.coordinator import (
    LinksysDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_returns_devices_keyed_by_mac(hass: HomeAssistant) -> None:
    """Test coordinator data is a dict of JNAPDevice keyed by MAC address."""
    entry = MockConfigEntry(domain="linksys_smart")
    client = AsyncMock(spec=JNAPClient)
    client.get_devices.return_value = GetDevicesResponse(
        devices=[
            JNAPDevice(mac="aa:bb:cc:dd:ee:ff", name="My Laptop"),
            JNAPDevice(mac="11:22:33:44:55:66", name="My Phone"),
        ]
    )
    coordinator = LinksysDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_refresh()
    assert coordinator.data == {
        "aa:bb:cc:dd:ee:ff": JNAPDevice(mac="aa:bb:cc:dd:ee:ff", name="My Laptop"),
        "11:22:33:44:55:66": JNAPDevice(mac="11:22:33:44:55:66", name="My Phone"),
    }


async def test_coordinator_raises_update_failed_on_error(hass: HomeAssistant) -> None:
    """Test that a JNAPError is converted to UpdateFailed by _async_update_data."""
    entry = MockConfigEntry(domain="linksys_smart")
    client = AsyncMock(spec=JNAPClient)
    client.get_devices.side_effect = JNAPError("Cannot connect")
    coordinator = LinksysDataUpdateCoordinator(hass, entry, client)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_raises_config_entry_auth_failed_on_unauthorized(
    hass: HomeAssistant,
) -> None:
    """Test that JNAPUnauthorizedError triggers a reauth flow via ConfigEntryAuthFailed."""
    entry = MockConfigEntry(domain="linksys_smart")
    client = AsyncMock(spec=JNAPClient)
    client.get_devices.side_effect = JNAPUnauthorizedError
    coordinator = LinksysDataUpdateCoordinator(hass, entry, client)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
