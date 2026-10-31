"""Test the MusicCast integration setup."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.yamaha_musiccast.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import TEST_DEVICE_ID, TEST_ZONE


@pytest.mark.usefixtures("mock_musiccast_device")
async def test_device_via_device_links(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a zone sub-device links to the main device via via_device_id.

    Only the switch platform is loaded so the main device is registered solely
    by the integration setup, exercising the via_device pre-registration.
    """
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yamaha_musiccast.PLATFORMS", [Platform.SWITCH]
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    main_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE_ID), mock_config_entry.entry_id
    )
    assert main_device is not None

    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{TEST_DEVICE_ID}_{TEST_ZONE}"), mock_config_entry.entry_id
    )
    assert zone_device is not None
    assert zone_device.via_device_id == main_device.id
