"""Tests for device models."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.grandstream_home.const import (
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DOMAIN,
)
from homeassistant.components.grandstream_home.device import (
    GDSDevice,
    GNSNASDevice,
    GrandstreamDevice,
)
from homeassistant.core import HomeAssistant


def test_device_register_create(hass: HomeAssistant) -> None:
    """Test Device register create."""
    device_registry = MagicMock()
    device_registry.devices = {}

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        device = GDSDevice(hass, "Front Door", "uid-1", "entry-1")
        device.set_ip_address("192.168.1.100")
        device.set_mac_address("AA:BB:CC:DD:EE:FF")
        device.set_firmware_version("1.0.0")

    assert device.device_type == DEVICE_TYPE_GDS
    assert device_registry.async_get_or_create.called


def test_device_register_update_existing(hass: HomeAssistant) -> None:
    """Test Device register update existing."""
    existing_device = MagicMock()
    existing_device.id = "existing"
    existing_device.identifiers = {(DOMAIN, "uid-2")}
    device_registry = MagicMock()
    device_registry.devices = {"existing": existing_device}

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        device = GNSNASDevice(hass, "NAS", "uid-2", "entry-2")
        device.set_mac_address("AA-BB-CC-DD-EE-FF")

    assert device.device_type == DEVICE_TYPE_GNS_NAS
    assert device_registry.async_get_or_create.called


def test_device_info_connections(hass: HomeAssistant) -> None:
    """Test Device info connections."""
    device_registry = MagicMock()
    device_registry.devices = {}

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        device = GrandstreamDevice(hass, "Device", "uid-3", "entry-3")
        device.device_type = DEVICE_TYPE_GDS
        device.set_mac_address("AA:BB:CC:DD:EE:FF")
        device.set_firmware_version("2.0.0")
        info = device.device_info

    assert info["identifiers"] == {(DOMAIN, "uid-3")}
    assert info["connections"] == {("mac", "aa:bb:cc:dd:ee:ff")}


def test_device_with_product_model(hass: HomeAssistant) -> None:
    """Test Device with product model."""
    device_registry = MagicMock()
    device_registry.devices = {}

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        device = GDSDevice(
            hass,
            "GDS3725",
            "uid-4",
            "entry-4",
            device_model="GDS",
            product_model="GDS3725",
        )
        device.set_ip_address("192.168.1.100")
        info = device.device_info

    assert device.product_model == "GDS3725"
    # Model should display product_model
    assert "GDS3725" in info["model"]


def test_device_display_model_priority(hass: HomeAssistant) -> None:
    """Test Device display model priority: product_model > device_model > device_type."""
    device_registry = MagicMock()
    device_registry.devices = {}

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        # Test with all three set
        device1 = GrandstreamDevice(
            hass,
            "Device1",
            "uid-5",
            "entry-5",
            device_model="GDS",
            product_model="GDS3727",
        )
        device1.device_type = DEVICE_TYPE_GDS
        assert device1._get_display_model() == "GDS3727"

        # Test with only device_model set
        device2 = GrandstreamDevice(
            hass,
            "Device2",
            "uid-6",
            "entry-6",
            device_model="GDS",
            product_model=None,
        )
        device2.device_type = DEVICE_TYPE_GDS
        assert device2._get_display_model() == "GDS"

        # Test with only device_type set
        device3 = GrandstreamDevice(
            hass,
            "Device3",
            "uid-7",
            "entry-7",
            device_model=None,
            product_model=None,
        )
        device3.device_type = DEVICE_TYPE_GDS
        assert device3._get_display_model() == DEVICE_TYPE_GDS


def test_device_model_includes_ip_address(hass: HomeAssistant) -> None:
    """Test Device model includes IP address when set."""
    device_registry = MagicMock()
    device_registry.devices = {}

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        device = GDSDevice(
            hass,
            "GDS3725",
            "uid-8",
            "entry-8",
            device_model="GDS",
            product_model="GDS3725",
        )
        device.set_ip_address("192.168.1.100")
        info = device.device_info

    # Model should include IP address
    assert "GDS3725" in info["model"]
    assert "192.168.1.100" in info["model"]
