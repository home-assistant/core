"""Fixtures for DLNA tests."""
from __future__ import annotations

from collections.abc import Iterable
from socket import AddressFamily  # pylint: disable=no-name-in-module
from unittest.mock import Mock, create_autospec, patch, seal

from async_upnp_client import UpnpDevice, UpnpFactory
import pytest

from homeassistant.components.dlna_dmr.const import DOMAIN as DLNA_DOMAIN
from homeassistant.components.dlna_dmr.data import DlnaDmrData
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DEVICE_BASE_URL = "http://192.88.99.4"
MOCK_DEVICE_LOCATION = MOCK_DEVICE_BASE_URL + "/dmr_description.xml"
MOCK_DEVICE_NAME = "Test Renderer Device"
MOCK_DEVICE_TYPE = "urn:schemas-upnp-org:device:MediaRenderer:1"
MOCK_DEVICE_UDN = "uuid:7cc6da13-7f5d-4ace-9729-58b275c52f1e"
MOCK_DEVICE_USN = f"{MOCK_DEVICE_UDN}::{MOCK_DEVICE_TYPE}"

LOCAL_IP = "192.88.99.1"
EVENT_CALLBACK_URL = "http://192.88.99.1/notify"

NEW_DEVICE_LOCATION = "http://192.88.99.7" + "/dmr_description.xml"


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
    seal(upnp_device)
    domain_data.upnp_factory.async_create_device.return_value = upnp_device

    domain_data.unmigrated_config = {}

    with patch.dict(hass.data, {DLNA_DOMAIN: domain_data}):
        yield domain_data

    # Make sure the event notifiers are released
    assert (
        domain_data.async_get_event_notifier.await_count
        == domain_data.async_release_event_notifier.await_count
    )


@pytest.fixture
def config_entry_mock() -> Iterable[MockConfigEntry]:
    """Mock a config entry for this platform."""
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
    yield mock_entry


@pytest.fixture
def dmr_device_mock(domain_data_mock: Mock) -> Iterable[Mock]:
    """Mock the async_upnp_client DMR device, initially connected."""
    with patch(
        "homeassistant.components.dlna_dmr.media_player.DmrDevice", autospec=True
    ) as constructor:
        device = constructor.return_value
        device.on_event = None
        device.device = domain_data_mock.upnp_factory.async_create_device.return_value
        device.media_image_url = "http://192.88.99.20:8200/AlbumArt/2624-17620.jpg"
        device.udn = "device_udn"
        device.manufacturer = "device_manufacturer"
        device.model_name = "device_model_name"
        device.name = "device_name"

        yield device

        # Make sure the device is disconnected
        assert (
            device.async_subscribe_services.await_count
            == device.async_unsubscribe_services.await_count
        )

        assert device.on_event is None


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture() -> Iterable[None]:
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


@pytest.fixture(autouse=True)
def ssdp_scanner_mock() -> Iterable[Mock]:
    """Mock the SSDP module."""
    with patch("homeassistant.components.ssdp.Scanner", autospec=True) as mock_scanner:
        reg_callback = mock_scanner.return_value.async_register_callback
        reg_callback.return_value = Mock(return_value=None)
        yield mock_scanner.return_value
        assert (
            reg_callback.call_count == reg_callback.return_value.call_count
        ), "Not all callbacks unregistered"


@pytest.fixture(autouse=True)
def async_get_local_ip_mock() -> Iterable[Mock]:
    """Mock the async_get_local_ip utility function to prevent network access."""
    with patch(
        "homeassistant.components.dlna_dmr.media_player.async_get_local_ip",
        autospec=True,
    ) as func:
        func.return_value = AddressFamily.AF_INET, LOCAL_IP
        yield func
