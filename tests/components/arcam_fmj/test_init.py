"""Tests for the Arcam FMJ config entry setup."""

import pytest

from homeassistant.components.arcam_fmj.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_UUID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("player_setup")
async def test_device_via_device_links(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the zone 2 device links to the zone 1 device via via_device_id."""
    zone1_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_UUID), mock_config_entry.entry_id
    )
    assert zone1_device is not None

    zone2_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_UUID}-2"), mock_config_entry.entry_id
    )
    assert zone2_device is not None
    assert zone2_device.via_device_id == zone1_device.id
