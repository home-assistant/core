"""Fixtures for DLNA tests."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.dlna_dmr.const import DOMAIN as DLNA_DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

GOOD_DEVICE_BASE_URL = "http://192.88.99.4"
GOOD_DEVICE_LOCATION = GOOD_DEVICE_BASE_URL + "/dmr_description.xml"
GOOD_DEVICE_NAME = "Test Receiver Device"
GOOD_DEVICE_TYPE = "urn:schemas-upnp-org:device:MediaRenderer:1"
GOOD_DEVICE_UDN = "uuid:7cc6da13-7f5d-4ace-9729-58b275c52f1e"
GOOD_DEVICE_USN = f"{GOOD_DEVICE_UDN}::{GOOD_DEVICE_TYPE}"

SUBSCRIPTION_UUID_RC = "uuid:204b8fdb-b953-4fa0-a08c-a08ad5856e93"
SUBSCRIPTION_UUID_AVT = "uuid:05724b15-036f-4c06-ab56-c884904056c7"

NEW_DEVICE_LOCATION = "http://192.88.99.7" + "/dmr_description.xml"

UNCONTACTABLE_DEVICE_LOCATION = "http://192.88.99.5/uncontactable.xml"

WRONG_ST_DEVICE_LOCATION = "http://192.88.99.6/igd_description.xml"


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture() -> Iterable[None]:
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


@pytest.fixture(autouse=True)
def mock_ssdp_scanner() -> Iterable[Mock]:
    """Mock the SSDP module."""
    with patch("homeassistant.components.ssdp.Scanner", autospec=True) as mock_scanner:
        yield mock_scanner.return_value


def configure_device_requests_mock(aioclient_mock: AiohttpClientMocker) -> None:
    """Add mock device responses to existing AiohttpClient mock."""
    description_xml = load_fixture("dlna_dmr/dmr_description.xml")
    aioclient_mock.get(GOOD_DEVICE_LOCATION, text=description_xml)
    rc_desc_xml = load_fixture("dlna_dmr/rc_desc.xml")
    aioclient_mock.get(
        GOOD_DEVICE_BASE_URL + "/RenderingControl/desc.xml", text=rc_desc_xml
    )
    cm_desc_xml = load_fixture("dlna_dmr/cm_desc.xml")
    aioclient_mock.get(
        GOOD_DEVICE_BASE_URL + "/ConnectionManager/desc.xml", text=cm_desc_xml
    )
    avt_desc_xml = load_fixture("dlna_dmr/avt_desc.xml")
    aioclient_mock.get(
        GOOD_DEVICE_BASE_URL + "/AVTransport/desc.xml", text=avt_desc_xml
    )

    aioclient_mock.request(
        "SUBSCRIBE",
        GOOD_DEVICE_BASE_URL + "/RenderingControl/evt",
        headers={"SID": SUBSCRIPTION_UUID_RC, "TIMEOUT": "Second-150"},
    )
    aioclient_mock.request(
        "SUBSCRIBE",
        GOOD_DEVICE_BASE_URL + "/AVTransport/evt",
        headers={"SID": SUBSCRIPTION_UUID_AVT, "TIMEOUT": "Second-150"},
    )
    aioclient_mock.request(
        "UNSUBSCRIBE", GOOD_DEVICE_BASE_URL + "/RenderingControl/evt"
    )
    aioclient_mock.request("UNSUBSCRIBE", GOOD_DEVICE_BASE_URL + "/AVTransport/evt")

    aioclient_mock.get(UNCONTACTABLE_DEVICE_LOCATION, exc=asyncio.TimeoutError)

    igd_desc_xml = load_fixture("dlna_dmr/igd_desc.xml")
    aioclient_mock.get(WRONG_ST_DEVICE_LOCATION, text=igd_desc_xml)


@pytest.fixture
def device_requests_mock(
    aioclient_mock: AiohttpClientMocker,
) -> Iterable[AiohttpClientMocker]:
    """Mock device responses to HTTP requests."""
    configure_device_requests_mock(aioclient_mock)
    yield aioclient_mock


@pytest.fixture
def config_entry_mock(hass: HomeAssistant) -> Iterable[MockConfigEntry]:
    """Mock a config entry for this platform."""
    config_entry = MockConfigEntry(
        unique_id=GOOD_DEVICE_UDN,
        domain=DLNA_DOMAIN,
        data={
            CONF_URL: GOOD_DEVICE_LOCATION,
            CONF_DEVICE_ID: GOOD_DEVICE_UDN,
            CONF_TYPE: GOOD_DEVICE_TYPE,
        },
        title=GOOD_DEVICE_NAME,
        options={},
    )
    config_entry.add_to_hass(hass)

    yield config_entry
