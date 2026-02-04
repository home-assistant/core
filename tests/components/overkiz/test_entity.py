"""Tests for Overkiz entity module."""

from unittest.mock import MagicMock, patch

from pyoverkiz.enums import UIClass, UIWidget
from pyoverkiz.models import Device
import pytest

from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.components.overkiz.entity import OverkizEntity


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.client.server.manufacturer = "Test Manufacturer"
    coordinator.client.server.configuration_url = "https://example.com"
    coordinator.areas = None
    return coordinator


def create_mock_device(
    device_url: str,
    label: str = "Test Device",
    controllable_name: str = "test:Component",
) -> Device:
    """Create a mock device."""
    device = MagicMock(spec=Device)
    device.device_url = device_url
    device.label = label
    device.controllable_name = controllable_name
    device.widget = UIWidget.UNKNOWN
    device.ui_class = UIClass.GENERIC
    device.place_oid = None
    device.states = {}
    device.attributes = {}
    device.available = True
    return device


class TestOverkizEntityDeviceInfo:
    """Test device info generation for Overkiz entities."""

    def test_parent_device_uses_base_url_as_identifier(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test parent device (#1) uses base URL as identifier."""
        device_url = "io://1234-5678-1234/device#1"
        device = create_mock_device(device_url, "Main Device")
        mock_coordinator.data = {device_url: device}

        with patch.object(OverkizEntity, "__init__", lambda x, y, z: None):
            entity = OverkizEntity.__new__(OverkizEntity)
            entity.device_url = device_url
            entity.base_device_url = "io://1234-5678-1234/device"
            entity.coordinator = mock_coordinator
            entity.executor = MagicMock()
            entity.executor.base_device_url = "io://1234-5678-1234/device"
            entity.executor.get_gateway_id.return_value = "1234-5678-1234"
            entity.executor.select_attribute.return_value = None
            entity.executor.select_state.return_value = None

            device_info = entity.generate_device_info()

        assert device_info["identifiers"] == {(DOMAIN, "io://1234-5678-1234/device")}
        assert device_info["via_device"] == (DOMAIN, "1234-5678-1234")

    def test_sub_device_uses_full_url_as_identifier(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test sub-device (#2, #3, etc.) uses full URL as identifier."""
        device_url = "io://1234-5678-1234/device#2"
        device = create_mock_device(device_url, "Zone 1 Thermostat")
        mock_coordinator.data = {device_url: device}

        with patch.object(OverkizEntity, "__init__", lambda x, y, z: None):
            entity = OverkizEntity.__new__(OverkizEntity)
            entity.device_url = device_url
            entity.base_device_url = "io://1234-5678-1234/device"
            entity.coordinator = mock_coordinator
            entity.executor = MagicMock()
            entity.executor.base_device_url = "io://1234-5678-1234/device"
            entity.executor.get_gateway_id.return_value = "1234-5678-1234"
            entity.executor.select_attribute.return_value = None
            entity.executor.select_state.return_value = None

            device_info = entity.generate_device_info()

        # Sub-device should have its own unique identifier
        assert device_info["identifiers"] == {(DOMAIN, "io://1234-5678-1234/device#2")}
        # Sub-device should link to parent device via via_device
        assert device_info["via_device"] == (
            DOMAIN,
            "io://1234-5678-1234/device",
        )
        assert device_info["name"] == "Zone 1 Thermostat"

    def test_multiple_sub_devices_have_unique_identifiers(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test multiple sub-devices each have unique identifiers."""
        base_url = "io://1234-5678-1234/device"
        device_urls = [f"{base_url}#2", f"{base_url}#3", f"{base_url}#4"]

        devices = {
            url: create_mock_device(url, f"Device {i}")
            for i, url in enumerate(device_urls, start=2)
        }
        mock_coordinator.data = devices

        device_infos = []
        for device_url in device_urls:
            with patch.object(OverkizEntity, "__init__", lambda x, y, z: None):
                entity = OverkizEntity.__new__(OverkizEntity)
                entity.device_url = device_url
                entity.base_device_url = base_url
                entity.coordinator = mock_coordinator
                entity.executor = MagicMock()
                entity.executor.base_device_url = base_url
                entity.executor.get_gateway_id.return_value = "1234-5678-1234"
                entity.executor.select_attribute.return_value = None
                entity.executor.select_state.return_value = None

                device_infos.append(entity.generate_device_info())

        # Each sub-device should have unique identifiers
        identifiers = [info["identifiers"] for info in device_infos]
        assert len(identifiers) == len({tuple(sorted(i)) for i in identifiers})

        # All sub-devices should link to the same parent
        for device_info in device_infos:
            assert device_info["via_device"] == (DOMAIN, base_url)

    def test_device_without_hash_uses_url_as_identifier(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test device without # suffix uses URL as identifier."""
        device_url = "io://1234-5678-1234/simple_device"
        device = create_mock_device(device_url, "Simple Device")
        mock_coordinator.data = {device_url: device}

        with patch.object(OverkizEntity, "__init__", lambda x, y, z: None):
            entity = OverkizEntity.__new__(OverkizEntity)
            entity.device_url = device_url
            entity.base_device_url = device_url
            entity.coordinator = mock_coordinator
            entity.executor = MagicMock()
            entity.executor.base_device_url = device_url
            entity.executor.get_gateway_id.return_value = "1234-5678-1234"
            entity.executor.select_attribute.return_value = None
            entity.executor.select_state.return_value = None

            device_info = entity.generate_device_info()

        assert device_info["identifiers"] == {
            (DOMAIN, "io://1234-5678-1234/simple_device")
        }
        # Non-sub-device links to gateway
        assert device_info["via_device"] == (DOMAIN, "1234-5678-1234")


class TestIsSubDevice:
    """Test is_sub_device property."""

    def test_device_with_hash_1_is_not_sub_device(self) -> None:
        """Test device ending with #1 is not considered a sub-device."""
        with patch.object(OverkizEntity, "__init__", lambda x, y, z: None):
            entity = OverkizEntity.__new__(OverkizEntity)
            entity.device_url = "io://1234-5678-1234/device#1"

            assert entity.is_sub_device is False

    def test_device_with_hash_2_is_sub_device(self) -> None:
        """Test device ending with #2 is considered a sub-device."""
        with patch.object(OverkizEntity, "__init__", lambda x, y, z: None):
            entity = OverkizEntity.__new__(OverkizEntity)
            entity.device_url = "io://1234-5678-1234/device#2"

            assert entity.is_sub_device is True

    def test_device_without_hash_is_not_sub_device(self) -> None:
        """Test device without # is not considered a sub-device."""
        with patch.object(OverkizEntity, "__init__", lambda x, y, z: None):
            entity = OverkizEntity.__new__(OverkizEntity)
            entity.device_url = "io://1234-5678-1234/device"

            assert entity.is_sub_device is False
