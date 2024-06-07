"""Fixtures for DLNA DMS tests."""

from __future__ import annotations

from collections.abc import AsyncIterable, Iterable
from typing import Final, cast
from unittest.mock import Mock, create_autospec, patch, seal

from async_upnp_client.client import UpnpDevice, UpnpService
from async_upnp_client.utils import absolute_url
import pytest

from homeassistant.components.dlna_dms.const import (
    CONF_SOURCE_ID,
    CONFIG_VERSION,
    DOMAIN,
)
from homeassistant.components.dlna_dms.dms import DlnaDmsData
from homeassistant.const import CONF_DEVICE_ID, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_DEVICE_HOST: Final = "192.88.99.21"
MOCK_DEVICE_BASE_URL: Final = f"http://{MOCK_DEVICE_HOST}"
MOCK_DEVICE_LOCATION: Final = MOCK_DEVICE_BASE_URL + "/dms_description.xml"
MOCK_DEVICE_NAME: Final = "Test Server Device"
MOCK_DEVICE_TYPE: Final = "urn:schemas-upnp-org:device:MediaServer:1"
MOCK_DEVICE_UDN: Final = "uuid:7bf34520-f034-4fa2-8d2d-2f709d4221ef"
MOCK_DEVICE_USN: Final = f"{MOCK_DEVICE_UDN}::{MOCK_DEVICE_TYPE}"
MOCK_SOURCE_ID: Final = "test_server_device"

LOCAL_IP: Final = "192.88.99.1"
EVENT_CALLBACK_URL: Final = "http://192.88.99.1/notify"

NEW_DEVICE_LOCATION: Final = "http://192.88.99.7" + "/dmr_description.xml"


@pytest.fixture
async def setup_media_source(hass) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


@pytest.fixture
def upnp_factory_mock() -> Iterable[Mock]:
    """Mock the UpnpFactory class to construct DMS-style UPnP devices."""
    with patch(
        "homeassistant.components.dlna_dms.dms.UpnpFactory",
        autospec=True,
        spec_set=True,
    ) as upnp_factory:
        upnp_device = create_autospec(UpnpDevice, instance=True)
        upnp_device.name = MOCK_DEVICE_NAME
        upnp_device.udn = MOCK_DEVICE_UDN
        upnp_device.device_url = MOCK_DEVICE_LOCATION
        upnp_device.device_type = MOCK_DEVICE_TYPE
        upnp_device.available = True
        upnp_device.parent_device = None
        upnp_device.root_device = upnp_device
        upnp_device.all_devices = [upnp_device]
        upnp_device.services = {
            "urn:schemas-upnp-org:service:ContentDirectory:1": create_autospec(
                UpnpService,
                instance=True,
                service_type="urn:schemas-upnp-org:service:ContentDirectory:1",
                service_id="urn:upnp-org:serviceId:ContentDirectory",
            ),
            "urn:schemas-upnp-org:service:ConnectionManager:1": create_autospec(
                UpnpService,
                instance=True,
                service_type="urn:schemas-upnp-org:service:ConnectionManager:1",
                service_id="urn:upnp-org:serviceId:ConnectionManager",
            ),
        }
        seal(upnp_device)
        upnp_factory_instance = upnp_factory.return_value
        upnp_factory_instance.async_create_device.return_value = upnp_device

        yield upnp_factory_instance


@pytest.fixture(autouse=True, scope="module")
def aiohttp_session_requester_mock() -> Iterable[Mock]:
    """Mock the AiohttpSessionRequester to prevent network use."""
    with patch(
        "homeassistant.components.dlna_dms.dms.AiohttpSessionRequester", autospec=True
    ) as requester_mock:
        yield requester_mock


@pytest.fixture
def config_entry_mock() -> MockConfigEntry:
    """Mock a config entry for this platform."""
    return MockConfigEntry(
        unique_id=MOCK_DEVICE_USN,
        domain=DOMAIN,
        version=CONFIG_VERSION,
        data={
            CONF_URL: MOCK_DEVICE_LOCATION,
            CONF_DEVICE_ID: MOCK_DEVICE_USN,
            CONF_SOURCE_ID: MOCK_SOURCE_ID,
        },
        title=MOCK_DEVICE_NAME,
    )


@pytest.fixture
def dms_device_mock(upnp_factory_mock: Mock) -> Iterable[Mock]:
    """Mock the async_upnp_client DMS device, initially connected."""
    with patch(
        "homeassistant.components.dlna_dms.dms.DmsDevice", autospec=True
    ) as constructor:
        device = constructor.return_value
        device.on_event = None
        device.profile_device = upnp_factory_mock.async_create_device.return_value
        device.icon = MOCK_DEVICE_BASE_URL + "/icon.jpg"
        device.udn = "device_udn"
        device.manufacturer = "device_manufacturer"
        device.model_name = "device_model_name"
        device.name = "device_name"
        device.get_absolute_url.side_effect = lambda url: absolute_url(
            MOCK_DEVICE_BASE_URL, url
        )

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


@pytest.fixture
async def device_source_mock(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dms_device_mock: Mock,
) -> AsyncIterable[None]:
    """Fixture to set up a DmsDeviceSource in a connected state and cleanup at completion."""
    config_entry_mock.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_mock.entry_id)
    await hass.async_block_till_done()

    # Check the DmsDeviceSource has registered all needed listeners
    assert len(config_entry_mock.update_listeners) == 0
    assert ssdp_scanner_mock.async_register_callback.await_count == 2
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 0

    # Run the test
    yield None

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Check DmsDeviceSource has cleaned up its resources
    assert not config_entry_mock.update_listeners
    assert (
        ssdp_scanner_mock.async_register_callback.await_count
        == ssdp_scanner_mock.async_register_callback.return_value.call_count
    )

    domain_data = cast(DlnaDmsData, hass.data[DOMAIN])
    assert MOCK_DEVICE_USN not in domain_data.devices
    assert MOCK_SOURCE_ID not in domain_data.sources
