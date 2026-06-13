"""Test the Eurotronic Comet Blue integration setup."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.eurotronic_cometblue.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FIXTURE_MAC
from .conftest import setup_with_selected_platforms

from tests.common import MockConfigEntry


async def test_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the Bluetooth connection."""
    await setup_with_selected_platforms(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, FIXTURE_MAC)})
    assert device_entry == snapshot
