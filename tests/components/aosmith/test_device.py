"""Tests for the device created by the A. O. Smith integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aosmith.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of the device."""
    reg_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "junctionId"), init_integration.entry_id
    )

    assert reg_device == snapshot
