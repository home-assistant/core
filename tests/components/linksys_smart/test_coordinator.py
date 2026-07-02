"""Test Linksys Smart Wi-Fi coordinator."""

from unittest.mock import AsyncMock

from jnap import (
    GetDevicesResponse,
    JNAPClient,
    JNAPDevice,
    JNAPError,
    JNAPUnauthorizedError,
)

from homeassistant.components.linksys_smart.coordinator import (
    LinksysDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
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


async def test_coordinator_sets_update_failed_on_error(hass: HomeAssistant) -> None:
    """Test that a JNAPError is converted to UpdateFailed and stored on the coordinator."""
    entry = MockConfigEntry(domain="linksys_smart")
    client = AsyncMock(spec=JNAPClient)
    client.get_devices.side_effect = JNAPError("Cannot connect")
    coordinator = LinksysDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_coordinator_sets_update_failed_on_unauthorized(
    hass: HomeAssistant,
) -> None:
    """Test that JNAPUnauthorizedError is converted to UpdateFailed on the coordinator."""
    entry = MockConfigEntry(domain="linksys_smart")
    client = AsyncMock(spec=JNAPClient)
    client.get_devices.side_effect = JNAPUnauthorizedError
    coordinator = LinksysDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
