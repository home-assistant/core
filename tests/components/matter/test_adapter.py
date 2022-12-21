"""Test the adapter."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.matter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import setup_integration_with_node_fixture


async def test_device_registry_single_node_device(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test bridge devices are set up correctly with via_device."""
    await setup_integration_with_node_fixture(
        hass,
        "onoff-light",
        matter_client,
    )

    dev_reg = dr.async_get(hass)

    entry = dev_reg.async_get_device({(DOMAIN, "mock-onoff-light")})
    assert entry is not None

    assert entry.name == "Mock OnOff Light"
    assert entry.manufacturer == "Nabu Casa"
    assert entry.model == "Mock Light"
    assert entry.hw_version == "v1.0"
    assert entry.sw_version == "v1.0"


@pytest.mark.skip("Waiting for a new test fixture")
async def test_device_registry_bridge(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test bridge devices are set up correctly with via_device."""
    await setup_integration_with_node_fixture(
        hass,
        "fake-bridge-two-light",
        matter_client,
    )

    dev_reg = dr.async_get(hass)

    # Validate bridge
    bridge_entry = dev_reg.async_get_device({(DOMAIN, "mock-hub-id")})
    assert bridge_entry is not None

    assert bridge_entry.name == "My Mock Bridge"
    assert bridge_entry.manufacturer == "Mock Vendor"
    assert bridge_entry.model == "Mock Bridge"
    assert bridge_entry.hw_version == "TEST_VERSION"
    assert bridge_entry.sw_version == "123.4.5"

    # Device 1
    device1_entry = dev_reg.async_get_device({(DOMAIN, "mock-id-kitchen-ceiling")})
    assert device1_entry is not None

    assert device1_entry.via_device_id == bridge_entry.id
    assert device1_entry.name == "Kitchen Ceiling"
    assert device1_entry.manufacturer == "Mock Vendor"
    assert device1_entry.model == "Mock Light"
    assert device1_entry.hw_version is None
    assert device1_entry.sw_version == "67.8.9"

    # Device 2
    device2_entry = dev_reg.async_get_device({(DOMAIN, "mock-id-living-room-ceiling")})
    assert device2_entry is not None

    assert device2_entry.via_device_id == bridge_entry.id
    assert device2_entry.name == "Living Room Ceiling"
    assert device2_entry.manufacturer == "Mock Vendor"
    assert device2_entry.model == "Mock Light"
    assert device2_entry.hw_version is None
    assert device2_entry.sw_version == "1.49.1"
