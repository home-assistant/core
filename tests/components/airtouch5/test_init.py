"""Test the AirTouch 5 config flow."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.airtouch5 import DOMAIN, update_device_id
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.conftest import MockConfigEntry


@pytest.mark.asyncio
async def test_update_device_id(hass: HomeAssistant) -> None:
    """Test updating device identifiers in the device registry."""

    mock_entry = MockConfigEntry(
        domain="airtouch5",
        data={CONF_HOST: "1.2.3.4"},
        unique_id="old_id",
        version=1,
        minor_version=1,
    )
    mock_entry.add_to_hass(hass)  # ✅ Add to hass

    # Mock airtouch device
    airtouch_device = MagicMock()
    airtouch_device.system_id = "sys123"

    # Create a device registry with various test cases
    device_registry = dr.async_get(hass)
    # Device not in our domain (should be skipped)
    device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={("other_domain", "other_1")},
        manufacturer="Test",
        model="T1",
        name="Other Device",
        sw_version="1.0",
    )

    # Device with zone_ prefix (should be updated)
    device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, "zone_1")},
        manufacturer="Test",
        model="T2",
        name="Zone Device",
        sw_version="1.0",
    )

    # Device with ac_ prefix (should be updated)
    device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, "ac_1")},
        manufacturer="Test",
        model="T3",
        name="AC Device",
        sw_version="1.0",
    )

    # Device with existing new identifier (should skip update)
    device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, "sys123_2")},
        manufacturer="Test",
        model="T4",
        name="Existing Device",
        sw_version="1.0",
    )
    # duplicate_device with same new identifier (should skip update and log warning)
    device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, "zone_2")},
        manufacturer="Test",
        model="T5",
        name="Duplicate Device",
        sw_version="1.0",
    )

    update_device_id(airtouch_device, device_registry)

    # Check zone_device was updated
    updated_zone = device_registry.async_get_device({(DOMAIN, "sys123_1")})
    assert updated_zone is not None

    # Check ac_device was updated
    updated_ac = device_registry.async_get_device({(DOMAIN, "sys123")})
    assert updated_ac is not None

    # Check duplicate device did not overwrite existing device
    updated_duplicate = device_registry.async_get_device({(DOMAIN, "sys123_2")})
    assert updated_duplicate is not None
