"""Fixtures for DLNA tests."""
from __future__ import annotations

from collections.abc import Iterable
from socket import AddressFamily  # pylint: disable=no-name-in-module
from unittest.mock import Mock, create_autospec, patch, seal

from async_upnp_client.client import UpnpDevice, UpnpService
from async_upnp_client.client_factory import UpnpFactory
import pytest

from homeassistant.components.dlna_dmr.const import DOMAIN as DLNA_DOMAIN
from homeassistant.components.dlna_dmr.data import DlnaDmrData
from homeassistant.const import CONF_DEVICE_ID, CONF_MAC, CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DEVICE_HOST_ADDR = "198.51.100.4"
MOCK_DEVICE_LOCATION = f"http://{MOCK_DEVICE_HOST_ADDR}/dmr_description.xml"
MOCK_DEVICE_NAME = "Test Renderer Device"
MOCK_DEVICE_TYPE = "urn:schemas-upnp-org:device:MediaRenderer:1"
MOCK_DEVICE_UDN = "uuid:7cc6da13-7f5d-4ace-9729-58b275c52f1e"
MOCK_DEVICE_USN = f"{MOCK_DEVICE_UDN}::{MOCK_DEVICE_TYPE}"
MOCK_MAC_ADDRESS = "ab:cd:ef:01:02:03"

LOCAL_IP = "198.51.100.1"
EVENT_CALLBACK_URL = "http://198.51.100.1/notify"

NEW_DEVICE_LOCATION = "http://198.51.100.7" + "/dmr_description.xml"


@pytest.fixture
def domain_data_mock(hass: HomeAssistant) -> Iterable[Mock]:
    """Mock the global data used by this component.

    This includes network clients and library object factories. Mocking it
    prevents network use.
    """
    domain_data = create_autospec(DlnaDmrData, instance=True)
    domain_data.upnp_factory = create_autospec(
        UpnpFactory, spec_set=True, instance=True
    )

    upnp_device = create_autospec(UpnpDevice, instance=True)
    upnp_device.name = MOCK_DEVICE_NAME
    upnp_device.udn = MOCK_DEVICE_UDN
    upnp_device.device_url = MOCK_DEVICE_LOCATION
    upnp_device.device_type = "urn:schemas-upnp-org:device:MediaRenderer:1"
    upnp_device.available = True
    upnp_device.parent_device = None
    upnp_device.root_device = upnp_device
    upnp_device.all_devices = [upnp_device]
    upnp_device.services = {
        "urn:schemas-upnp-org:service:AVTransport:1": create_autospec(
            UpnpService,
            instance=True,
            service_type="urn:schemas-upnp-org:service:AVTransport:1",
            service_id="urn:upnp-org:serviceId:AVTransport",
        ),
        "urn:schemas-upnp-org:service:ConnectionManager:1": create_autospec(
            UpnpService,
            instance=True,
            service_type="urn:schemas-upnp-org:service:ConnectionManager:1",
            service_id="urn:upnp-org:serviceId:ConnectionManager",
        ),
        "urn:schemas-upnp-org:service:RenderingControl:1": create_autospec(
            UpnpService,
            instance=True,
            service_type="urn:schemas-upnp-org:service:RenderingControl:1",
            service_id="urn:upnp-org:serviceId:RenderingControl",
        ),
    }
    seal(upnp_device)
    domain_data.upnp_factory.async_create_device.return_value = upnp_device

    hass.data[DLNA_DOMAIN] = domain_data
    return domain_data


@pytest.fixture
def config_entry_mock() -> MockConfigEntry:
    """Mock a config entry for this platform."""
    mock_entry = MockConfigEntry(
        unique_id=MOCK_DEVICE_UDN,
        domain=DLNA_DOMAIN,
        data={
            CONF_URL: MOCK_DEVICE_LOCATION,
            CONF_DEVICE_ID: MOCK_DEVICE_UDN,
            CONF_TYPE: MOCK_DEVICE_TYPE,
            CONF_MAC: MOCK_MAC_ADDRESS,
        },
        title=MOCK_DEVICE_NAME,
        options={},
    )
    return mock_entry


@pytest.fixture
def config_entry_mock_no_mac() -> MockConfigEntry:
    """Mock a config entry that does not already contain a MAC address."""
    mock_entry = MockConfigEntry(
        unique_id=MOCK_DEVICE_UDN,
        domain=DLNA_DOMAIN,
        data={
            CONF_URL: MOCK_DEVICE_LOCATION,
            CONF_DEVICE_ID: MOCK_DEVICE_UDN,
            CONF_TYPE: MOCK_DEVICE_TYPE,
        },
        title=MOCK_DEVICE_NAME,
        options={},
    )
    return mock_entry


@pytest.fixture
def dmr_device_mock(domain_data_mock: Mock) -> Iterable[Mock]:
    """Mock the async_upnp_client DMR device, initially connected."""
    with patch(
        "homeassistant.components.dlna_dmr.media_player.DmrDevice", autospec=True
    ) as constructor:
        device = constructor.return_value
        device.on_event = None
        device.profile_device = (
            domain_data_mock.upnp_factory.async_create_device.return_value
        )
        device.media_image_url = "http://198.51.100.20:8200/AlbumArt/2624-17620.jpg"
        device.udn = "device_udn"
        device.manufacturer = "device_manufacturer"
        device.model_name = "device_model_name"
        device.name = "device_name"
        device.preset_names = ["preset1", "preset2"]

        yield device


@pytest.fixture(autouse=True)
def ssdp_scanner_mock() -> Iterable[Mock]:
    """Mock the SSDP Scanner."""
    with patch("homeassistant.components.ssdp.Scanner", autospec=True) as mock_scanner:
        reg_callback = mock_scanner.return_value.async_register_callback
        reg_callback.return_value = Mock(return_value=None)
        yield mock_scanner.return_value


@pytest.fixture(autouse=True)
def ssdp_server_mock() -> Iterable[Mock]:
    """Mock the SSDP Server."""
    with patch("homeassistant.components.ssdp.Server", autospec=True):
        yield


@pytest.fixture(autouse=True)
def async_get_local_ip_mock() -> Iterable[Mock]:
    """Mock the async_get_local_ip utility function to prevent network access."""
    with patch(
        "homeassistant.components.dlna_dmr.media_player.async_get_local_ip",
        autospec=True,
    ) as func:
        func.return_value = AddressFamily.AF_INET, LOCAL_IP
        yield func


@pytest.fixture(autouse=True)
def dlna_dmr_mock_get_source_ip(mock_get_source_ip):
    """Mock network util's async_get_source_ip."""
