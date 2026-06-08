"""Test AirVisual Pro setup."""

from unittest.mock import Mock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airvisual_pro.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_device_registry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    pro: Mock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    with patch("homeassistant.components.airvisual_pro.NodeSamba", return_value=pro):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "XXXXXXX")})
    assert device_entry == snapshot
